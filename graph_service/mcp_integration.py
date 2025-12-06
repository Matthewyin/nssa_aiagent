"""
MCP 集成模块
提供全局的 MCP Manager 实例管理
"""

from typing import Optional
from loguru import logger
from mcp_manager import McpClientManager


# 全局 MCP Manager 实例
_mcp_manager: Optional[McpClientManager] = None


async def get_mcp_manager() -> McpClientManager:
    """
    获取或创建 MCP Manager 实例
    
    Returns:
        McpClientManager 实例
    """
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = McpClientManager()
        await _mcp_manager.start_all_servers()
        logger.info("MCP Manager 全局实例初始化完成")
    return _mcp_manager


async def shutdown_mcp_manager():
    """关闭 MCP Manager"""
    global _mcp_manager
    if _mcp_manager is not None:
        await _mcp_manager.stop_all_servers()
        _mcp_manager = None
        logger.info("MCP Manager 已关闭")


def get_mcp_manager_sync() -> Optional[McpClientManager]:
    """
    同步获取 MCP Manager 实例（如果已初始化）
    
    Returns:
        McpClientManager 实例或 None
    """
    return _mcp_manager

