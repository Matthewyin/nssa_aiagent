"""
ServerRegistry - 服务注册表
管理 MCP Server 的注册信息和健康状态
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import yaml

from utils.logger import get_logger

logger = get_logger(__name__)


class ServerStatus(Enum):
    """Server 状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class ServerInstance:
    """Server 实例信息"""
    name: str  # Server 名称
    description: str = ""
    environment: str = "default"
    weight: int = 100  # 权重（用于负载均衡）
    config_ref: Optional[str] = None  # 引用 mcp_config.yaml 中的配置
    
    # 状态信息
    status: ServerStatus = ServerStatus.UNKNOWN
    last_heartbeat: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    
    # 健康检查统计
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    
    # 提供的工具列表
    tools: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "environment": self.environment,
            "weight": self.weight,
            "config_ref": self.config_ref,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "tools": self.tools,
            "stats": {
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "success_rate": (1 - self.failed_requests / self.total_requests) * 100 
                    if self.total_requests > 0 else 100.0
            }
        }


class ServerRegistry:
    """服务注册表 - 管理 MCP Server 的注册信息和健康状态"""
    
    _instance: Optional["ServerRegistry"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self.servers: Dict[str, ServerInstance] = {}  # name -> ServerInstance
        self.tool_to_servers: Dict[str, List[str]] = {}  # tool_name -> [server_names]
        
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 心跳检查任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # 加载静态配置的 Server
        self._load_static_servers()
        
        logger.info(f"ServerRegistry 初始化完成，已加载 {len(self.servers)} 个 Server")
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "server_registry.yaml"
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载 ServerRegistry 配置失败: {e}")
            return {}
    
    def _load_static_servers(self):
        """从配置加载静态 Server"""
        static_servers = self.config.get("static_servers", [])
        
        for server_config in static_servers:
            server = ServerInstance(
                name=server_config.get("name"),
                description=server_config.get("description", ""),
                environment=server_config.get("environment", "default"),
                weight=server_config.get("weight", 100),
                config_ref=server_config.get("config_ref"),
                status=ServerStatus.UNKNOWN,
                registered_at=datetime.now(),
            )
            self.servers[server.name] = server
            logger.debug(f"加载静态 Server: {server.name}")
    
    def register(
        self,
        name: str,
        description: str = "",
        environment: str = "default",
        weight: int = 100,
        tools: List[str] = None,
    ) -> ServerInstance:
        """注册 Server"""
        now = datetime.now()
        
        if name in self.servers:
            # 更新已有 Server
            server = self.servers[name]
            server.description = description
            server.environment = environment
            server.weight = weight
            server.status = ServerStatus.HEALTHY
            server.last_heartbeat = now
            if tools:
                server.tools = tools
            logger.info(f"更新 Server 注册: {name}")
        else:
            # 新注册
            server = ServerInstance(
                name=name,
                description=description,
                environment=environment,
                weight=weight,
                status=ServerStatus.HEALTHY,
                last_heartbeat=now,
                registered_at=now,
                tools=tools or [],
            )
            self.servers[name] = server
            logger.info(f"新 Server 注册: {name}")
        
        # 更新工具映射
        self._update_tool_mapping(name, tools or [])

        return server

    def _update_tool_mapping(self, server_name: str, tools: List[str]):
        """更新工具到 Server 的映射"""
        # 移除旧的映射
        for tool_name, server_list in list(self.tool_to_servers.items()):
            if server_name in server_list:
                server_list.remove(server_name)
                if not server_list:
                    del self.tool_to_servers[tool_name]

        # 添加新的映射
        for tool_name in tools:
            if tool_name not in self.tool_to_servers:
                self.tool_to_servers[tool_name] = []
            if server_name not in self.tool_to_servers[tool_name]:
                self.tool_to_servers[tool_name].append(server_name)

    def heartbeat(self, name: str) -> bool:
        """处理心跳"""
        if name not in self.servers:
            logger.warning(f"收到未知 Server 的心跳: {name}")
            return False

        server = self.servers[name]
        server.last_heartbeat = datetime.now()
        server.status = ServerStatus.HEALTHY
        server.consecutive_failures = 0
        server.consecutive_successes += 1

        logger.debug(f"收到心跳: {name}")
        return True

    def deregister(self, name: str) -> bool:
        """注销 Server"""
        if name not in self.servers:
            return False

        server = self.servers.pop(name)

        # 移除工具映射
        self._update_tool_mapping(name, [])

        logger.info(f"Server 注销: {name}")
        return True

    def get_server(self, name: str) -> Optional[ServerInstance]:
        """获取 Server 信息"""
        return self.servers.get(name)

    def get_healthy_servers(self, environment: str = None) -> List[ServerInstance]:
        """获取健康的 Server 列表"""
        result = []
        for server in self.servers.values():
            if server.status != ServerStatus.HEALTHY:
                continue
            if environment and server.environment != environment:
                continue
            result.append(server)
        return result

    def get_servers_for_tool(self, tool_name: str) -> List[ServerInstance]:
        """获取提供指定工具的 Server 列表"""
        server_names = self.tool_to_servers.get(tool_name, [])
        return [
            self.servers[name]
            for name in server_names
            if name in self.servers and self.servers[name].status == ServerStatus.HEALTHY
        ]

    def mark_unhealthy(self, name: str):
        """标记 Server 为不健康"""
        if name in self.servers:
            server = self.servers[name]
            server.consecutive_failures += 1
            server.consecutive_successes = 0

            # 获取配置的阈值
            unhealthy_threshold = self.config.get("health_check", {}).get("unhealthy_threshold", 3)

            if server.consecutive_failures >= unhealthy_threshold:
                server.status = ServerStatus.UNHEALTHY
                logger.warning(f"Server {name} 标记为不健康 (连续失败 {server.consecutive_failures} 次)")

    def mark_healthy(self, name: str):
        """标记 Server 为健康"""
        if name in self.servers:
            server = self.servers[name]
            server.consecutive_successes += 1
            server.consecutive_failures = 0

            # 获取配置的阈值
            healthy_threshold = self.config.get("health_check", {}).get("healthy_threshold", 2)

            if server.consecutive_successes >= healthy_threshold:
                if server.status != ServerStatus.HEALTHY:
                    server.status = ServerStatus.HEALTHY
                    logger.info(f"Server {name} 恢复健康")

    def record_request(self, name: str, success: bool):
        """记录请求统计"""
        if name in self.servers:
            server = self.servers[name]
            server.total_requests += 1
            if not success:
                server.failed_requests += 1

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有 Server"""
        return [server.to_dict() for server in self.servers.values()]

    async def start_heartbeat_checker(self):
        """启动心跳检查任务"""
        if self._heartbeat_task is not None:
            return

        self._heartbeat_task = asyncio.create_task(self._heartbeat_check_loop())
        logger.info("心跳检查任务已启动")

    async def stop_heartbeat_checker(self):
        """停止心跳检查任务"""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            logger.info("心跳检查任务已停止")

    async def _heartbeat_check_loop(self):
        """心跳检查循环"""
        heartbeat_config = self.config.get("heartbeat", {})
        probe_interval = heartbeat_config.get("probe_interval_seconds", 10)
        timeout_seconds = heartbeat_config.get("timeout_seconds", 90)
        offline_threshold = heartbeat_config.get("offline_threshold_seconds", 180)

        while True:
            try:
                await asyncio.sleep(probe_interval)
                now = datetime.now()

                for server in self.servers.values():
                    if server.last_heartbeat is None:
                        continue

                    elapsed = (now - server.last_heartbeat).total_seconds()

                    if elapsed > offline_threshold:
                        if server.status != ServerStatus.OFFLINE:
                            server.status = ServerStatus.OFFLINE
                            logger.warning(f"Server {server.name} 已下线 (超时 {elapsed:.0f}s)")
                    elif elapsed > timeout_seconds:
                        if server.status == ServerStatus.HEALTHY:
                            server.status = ServerStatus.UNHEALTHY
                            logger.warning(f"Server {server.name} 心跳超时 (超时 {elapsed:.0f}s)")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检查出错: {e}")

