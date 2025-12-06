"""
核心功能测试
覆盖：配置加载、ToolGateway、ServerRegistry、API 接口
"""
import pytest
import asyncio
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestConfigManager:
    """配置管理器测试"""

    def test_load_llm_config(self):
        """测试 LLM 配置加载"""
        # 直接导入 ConfigManager，避免触发 utils/__init__.py 的 watchdog 导入
        import sys
        sys.path.insert(0, str(project_root))
        from utils.config_manager import ConfigManager

        config_manager = ConfigManager()
        config = config_manager.load_config("llm_config")

        assert config is not None
        assert "llm" in config
        assert "provider" in config["llm"]

    def test_load_mcp_config(self):
        """测试 MCP 配置加载"""
        from utils.config_manager import ConfigManager
        config_manager = ConfigManager()
        config = config_manager.load_config("mcp_config")

        assert config is not None
        # 配置文件中的键是 mcp_servers
        assert "mcp_servers" in config


class TestToolCatalog:
    """工具目录测试"""
    
    def test_catalog_load(self):
        """测试工具目录加载"""
        from tool_gateway import ToolCatalog
        catalog = ToolCatalog()
        
        # 目录应该能加载成功
        assert catalog is not None
    
    def test_get_binding(self):
        """测试获取工具绑定"""
        from tool_gateway import ToolCatalog
        catalog = ToolCatalog()
        
        # 尝试获取一个已配置的工具绑定
        binding = catalog.get_binding("network.ping")
        # 可能存在也可能不存在，取决于配置
        # 这里只测试方法不抛异常


class TestServerRegistry:
    """服务注册表测试"""
    
    def test_registry_singleton(self):
        """测试注册表单例"""
        from tool_gateway import ServerRegistry
        registry1 = ServerRegistry()
        registry2 = ServerRegistry()
        
        assert registry1 is registry2
    
    def test_register_server(self):
        """测试服务注册"""
        from tool_gateway import ServerRegistry, ServerStatus
        registry = ServerRegistry()

        # 注册一个测试服务（使用参数形式）
        server = registry.register(
            name="test-server-unit",
            description="单元测试服务",
            environment="test",
            tools=["test.tool1"]
        )

        # 验证注册成功
        retrieved = registry.get_server("test-server-unit")
        assert retrieved is not None
        assert retrieved.name == "test-server-unit"

        # 清理
        registry.deregister("test-server-unit")

    def test_heartbeat(self):
        """测试心跳"""
        from tool_gateway import ServerRegistry, ServerStatus
        registry = ServerRegistry()

        # 注册服务
        registry.register(
            name="test-server-hb",
            description="心跳测试服务",
            environment="test"
        )

        # 发送心跳
        result = registry.heartbeat("test-server-hb")
        assert result is True

        # 验证状态
        retrieved = registry.get_server("test-server-hb")
        assert retrieved.status == ServerStatus.HEALTHY

        # 清理
        registry.deregister("test-server-hb")


class TestRoutingStrategies:
    """路由策略测试"""
    
    def test_round_robin(self):
        """测试轮询策略"""
        from tool_gateway.router import RoundRobinStrategy
        from tool_gateway import ServerInstance
        
        strategy = RoundRobinStrategy()
        servers = [
            ServerInstance(name="s1", environment="test"),
            ServerInstance(name="s2", environment="test"),
            ServerInstance(name="s3", environment="test"),
        ]
        
        # 连续选择应该轮询
        names = [strategy.select(servers, {}).name for _ in range(6)]
        assert names == ["s1", "s2", "s3", "s1", "s2", "s3"]
    
    def test_weighted(self):
        """测试权重策略"""
        from tool_gateway.router import WeightedStrategy
        from tool_gateway import ServerInstance

        strategy = WeightedStrategy()
        servers = [
            ServerInstance(name="s1", environment="test", weight=100),
            ServerInstance(name="s2", environment="test", weight=1),
        ]

        # 权重高的应该被选中更多
        counts = {"s1": 0, "s2": 0}
        for _ in range(100):
            selected = strategy.select(servers, {})
            counts[selected.name] += 1

        # s1 的权重是 s2 的 100 倍，所以 s1 应该被选中更多
        assert counts["s1"] > counts["s2"]


class TestToolGateway:
    """工具网关测试"""
    
    def test_gateway_init(self):
        """测试网关初始化"""
        from tool_gateway import ToolGateway
        gateway = ToolGateway()
        
        assert gateway is not None
        assert gateway.catalog is not None
        assert gateway.registry is not None
        assert gateway.audit_logger is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

