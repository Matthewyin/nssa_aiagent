"""
路由策略模块
实现轮询、权重、一致性哈希等负载均衡策略
"""

import hashlib
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from bisect import bisect_left

from utils.logger import get_logger
from .registry import ServerInstance

logger = get_logger(__name__)


class RoutingStrategy(ABC):
    """路由策略抽象基类"""
    
    @abstractmethod
    def select(
        self,
        servers: List[ServerInstance],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServerInstance]:
        """
        从服务器列表中选择一个
        
        Args:
            servers: 可用服务器列表
            params: 调用参数（用于一致性哈希等策略）
        
        Returns:
            选中的服务器，如果没有可用服务器则返回 None
        """
        pass


class RoundRobinStrategy(RoutingStrategy):
    """轮询策略"""
    
    def __init__(self):
        self._counters: Dict[str, int] = {}  # tool_name -> counter
    
    def select(
        self,
        servers: List[ServerInstance],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServerInstance]:
        if not servers:
            return None
        
        # 使用服务器列表的第一个名字作为 key（简化处理）
        key = "_".join(sorted(s.name for s in servers))
        
        if key not in self._counters:
            self._counters[key] = 0
        
        index = self._counters[key] % len(servers)
        self._counters[key] += 1
        
        return servers[index]


class WeightedStrategy(RoutingStrategy):
    """权重策略"""
    
    def __init__(self, default_weight: int = 100):
        self.default_weight = default_weight
    
    def select(
        self,
        servers: List[ServerInstance],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServerInstance]:
        if not servers:
            return None
        
        # 构建权重列表
        weights = [s.weight if s.weight > 0 else self.default_weight for s in servers]
        total = sum(weights)
        
        if total == 0:
            return random.choice(servers)
        
        # 按权重随机选择
        r = random.uniform(0, total)
        cumulative = 0
        for server, weight in zip(servers, weights):
            cumulative += weight
            if r <= cumulative:
                return server
        
        return servers[-1]


class ConsistentHashStrategy(RoutingStrategy):
    """一致性哈希策略"""
    
    def __init__(self, virtual_nodes: int = 150, hash_fields: List[str] = None):
        self.virtual_nodes = virtual_nodes
        self.hash_fields = hash_fields or ["target", "query", "domain"]
        self._ring: List[int] = []
        self._nodes: Dict[int, str] = {}  # hash -> server_name
        self._built_for: Optional[str] = None  # 记录上次构建的服务器列表签名
    
    def _build_ring(self, servers: List[ServerInstance]):
        """构建哈希环"""
        signature = ",".join(sorted(s.name for s in servers))
        if self._built_for == signature:
            return
        
        self._ring = []
        self._nodes = {}
        
        for server in servers:
            for i in range(self.virtual_nodes):
                key = f"{server.name}:{i}"
                h = self._hash(key)
                self._ring.append(h)
                self._nodes[h] = server.name
        
        self._ring.sort()
        self._built_for = signature
        logger.debug(f"构建一致性哈希环: {len(servers)} 个节点, {len(self._ring)} 个虚拟节点")
    
    def _hash(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def _get_hash_key(self, params: Optional[Dict[str, Any]]) -> str:
        """从参数中提取用于哈希的 key"""
        if not params:
            return str(random.random())
        
        # 尝试从配置的字段中提取
        for field in self.hash_fields:
            if field in params and params[field]:
                return str(params[field])
        
        # 如果没有找到，使用所有参数的组合
        return str(sorted(params.items()))
    
    def select(
        self,
        servers: List[ServerInstance],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServerInstance]:
        if not servers:
            return None
        
        if len(servers) == 1:
            return servers[0]
        
        # 构建哈希环
        self._build_ring(servers)
        
        # 计算参数的哈希值
        key = self._get_hash_key(params)
        h = self._hash(key)
        
        # 在环上找到第一个大于等于 h 的节点
        idx = bisect_left(self._ring, h)
        if idx >= len(self._ring):
            idx = 0
        
        server_name = self._nodes[self._ring[idx]]
        
        # 返回对应的服务器
        for server in servers:
            if server.name == server_name:
                return server

        return servers[0]


class RandomStrategy(RoutingStrategy):
    """随机策略"""

    def select(
        self,
        servers: List[ServerInstance],
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServerInstance]:
        if not servers:
            return None
        return random.choice(servers)


class RoutingStrategyFactory:
    """路由策略工厂"""

    _strategies: Dict[str, RoutingStrategy] = {}

    @classmethod
    def get(cls, strategy_name: str, config: Optional[Dict[str, Any]] = None) -> RoutingStrategy:
        """
        获取路由策略实例

        Args:
            strategy_name: 策略名称 (round_robin, weighted, consistent_hash, random)
            config: 策略配置

        Returns:
            路由策略实例
        """
        config = config or {}

        # 使用缓存的实例（对于无状态策略）
        if strategy_name in ["random"]:
            if strategy_name not in cls._strategies:
                cls._strategies[strategy_name] = RandomStrategy()
            return cls._strategies[strategy_name]

        # 需要配置的策略，每次创建新实例（或带配置的缓存）
        cache_key = f"{strategy_name}:{hash(str(sorted(config.items())))}"

        if cache_key not in cls._strategies:
            if strategy_name == "round_robin":
                cls._strategies[cache_key] = RoundRobinStrategy()
            elif strategy_name == "weighted":
                default_weight = config.get("default_weight", 100)
                cls._strategies[cache_key] = WeightedStrategy(default_weight=default_weight)
            elif strategy_name == "consistent_hash":
                virtual_nodes = config.get("virtual_nodes", 150)
                hash_fields = config.get("hash_fields", ["target", "query", "domain"])
                cls._strategies[cache_key] = ConsistentHashStrategy(
                    virtual_nodes=virtual_nodes,
                    hash_fields=hash_fields,
                )
            else:
                # 默认使用轮询
                logger.warning(f"未知的路由策略: {strategy_name}，使用 round_robin")
                cls._strategies[cache_key] = RoundRobinStrategy()

        return cls._strategies[cache_key]

