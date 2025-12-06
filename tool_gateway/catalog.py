"""
ToolCatalog - 工具目录
负责加载和管理逻辑工具名到物理端点的映射
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from utils.logger import get_logger
from .models import ToolDefinition, ToolBinding, ToolPermission

logger = get_logger(__name__)


class ToolCatalog:
    """工具目录 - 管理逻辑工具名到物理端点的映射"""
    
    _instance: Optional["ToolCatalog"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化工具目录
        
        Args:
            config_path: 配置文件路径，默认为 config/tool_catalog.yaml
        """
        if self._initialized:
            return
        
        self._initialized = True
        self.tools: Dict[str, ToolDefinition] = {}
        self.physical_to_logical: Dict[str, str] = {}  # 物理工具名 → 逻辑工具名
        
        # 加载配置
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "tool_catalog.yaml"
        
        self._load_config(config_path)
        logger.info(f"ToolCatalog 初始化完成，加载了 {len(self.tools)} 个工具")
    
    def _load_config(self, config_path: str):
        """加载配置文件"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            tools_config = config.get("tools", {})
            
            for tool_key, tool_data in tools_config.items():
                # 解析 bindings
                bindings = []
                for binding_data in tool_data.get("bindings", []):
                    binding = ToolBinding(
                        mcp_server=binding_data.get("mcp_server"),
                        physical_tool=binding_data.get("physical_tool"),
                        environment=binding_data.get("environment", "default"),
                        priority=binding_data.get("priority", 1),
                        enabled=binding_data.get("enabled", True),
                    )
                    bindings.append(binding)
                
                # 解析 permissions
                perm_data = tool_data.get("permissions", {})
                permissions = ToolPermission(
                    allowed_agents=perm_data.get("allowed_agents", []),
                    require_confirmation=perm_data.get("require_confirmation", False),
                    dangerous_patterns=perm_data.get("dangerous_patterns", []),
                )
                
                # 创建 ToolDefinition
                tool_def = ToolDefinition(
                    logical_name=tool_data.get("logical_name", tool_key),
                    description=tool_data.get("description", ""),
                    category=tool_data.get("category", ""),
                    tags=tool_data.get("tags", []),
                    bindings=bindings,
                    input_schema=tool_data.get("input_schema", {}),
                    permissions=permissions,
                )
                
                # 注册工具
                self.tools[tool_def.logical_name] = tool_def
                
                # 建立反向映射
                for binding in bindings:
                    self.physical_to_logical[binding.physical_tool] = tool_def.logical_name
                
                logger.debug(f"加载工具: {tool_def.logical_name} -> {[b.physical_tool for b in bindings]}")
        
        except Exception as e:
            logger.error(f"加载 ToolCatalog 配置失败: {e}")
            raise
    
    def get_tool(self, logical_name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self.tools.get(logical_name)
    
    def get_binding(self, logical_name: str, environment: str = "default") -> Optional[ToolBinding]:
        """
        获取工具绑定（用于确定实际调用哪个物理端点）
        
        Args:
            logical_name: 逻辑工具名
            environment: 环境标识
        
        Returns:
            优先级最高的启用的绑定
        """
        tool = self.get_tool(logical_name)
        if not tool:
            return None
        
        # 筛选启用的、匹配环境的绑定
        enabled_bindings = [
            b for b in tool.bindings
            if b.enabled and b.environment == environment
        ]
        
        if not enabled_bindings:
            # 回退到 default 环境
            enabled_bindings = [
                b for b in tool.bindings
                if b.enabled and b.environment == "default"
            ]
        
        if not enabled_bindings:
            return None
        
        # 按优先级排序，返回最高优先级的
        enabled_bindings.sort(key=lambda b: b.priority, reverse=True)
        return enabled_bindings[0]
    
    def get_logical_name(self, physical_tool: str) -> Optional[str]:
        """根据物理工具名获取逻辑工具名"""
        return self.physical_to_logical.get(physical_tool)
    
    def list_tools(self, category: str = None, tags: List[str] = None) -> List[ToolDefinition]:
        """列出工具"""
        result = list(self.tools.values())
        
        if category:
            result = [t for t in result if t.category == category]
        
        if tags:
            result = [t for t in result if any(tag in t.tags for tag in tags)]
        
        return result
    
    def reload(self, config_path: Optional[str] = None):
        """重新加载配置"""
        self.tools.clear()
        self.physical_to_logical.clear()
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "tool_catalog.yaml"
        
        self._load_config(config_path)
        logger.info(f"ToolCatalog 重新加载完成，加载了 {len(self.tools)} 个工具")

