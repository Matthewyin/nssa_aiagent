"""
ToolGateway 数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class ToolCallStatus(Enum):
    """工具调用状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ToolBinding:
    """工具绑定 - 逻辑工具到物理端点的映射"""
    mcp_server: str  # MCP Server 名称
    physical_tool: str  # 物理工具名（如 network.ping）
    environment: str = "default"  # 环境标识
    priority: int = 1  # 优先级（用于负载均衡）
    enabled: bool = True  # 是否启用


@dataclass
class ToolPermission:
    """工具权限配置"""
    allowed_agents: List[str] = field(default_factory=list)  # 允许的 Agent 列表
    require_confirmation: bool = False  # 是否需要人工确认
    dangerous_patterns: List[str] = field(default_factory=list)  # 危险操作模式


@dataclass
class ToolDefinition:
    """工具定义"""
    logical_name: str  # 逻辑工具名
    description: str  # 工具描述
    category: str  # 工具分类
    tags: List[str]  # 标签
    bindings: List[ToolBinding]  # 物理端点绑定列表
    input_schema: Dict[str, Any] = field(default_factory=dict)  # 输入参数 schema
    permissions: Optional[ToolPermission] = None  # 权限配置


@dataclass
class ToolCallRequest:
    """工具调用请求"""
    logical_name: str  # 逻辑工具名
    params: Dict[str, Any]  # 调用参数
    caller_agent: str  # 调用者 Agent
    session_id: Optional[str] = None  # 会话 ID
    request_id: Optional[str] = None  # 请求 ID
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.request_id:
            import uuid
            self.request_id = str(uuid.uuid4())[:8]


@dataclass
class ToolCallResult:
    """工具调用结果"""
    request_id: str  # 请求 ID
    logical_name: str  # 逻辑工具名
    physical_tool: str  # 实际调用的物理工具
    mcp_server: str  # 实际调用的 MCP Server
    status: ToolCallStatus  # 调用状态
    result: Any = None  # 返回结果
    error: Optional[str] = None  # 错误信息
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None  # 耗时（毫秒）
    
    def complete(self, status: ToolCallStatus, result: Any = None, error: str = None):
        """完成调用"""
        self.end_time = datetime.now()
        self.status = status
        self.result = result
        self.error = error
        if self.start_time and self.end_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class AuditRecord:
    """审计记录"""
    request_id: str
    session_id: Optional[str]
    caller_agent: str
    logical_name: str
    physical_tool: str
    mcp_server: str
    params: Dict[str, Any]
    status: ToolCallStatus
    result_summary: Optional[str]  # 结果摘要（截断）
    error: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "caller_agent": self.caller_agent,
            "logical_name": self.logical_name,
            "physical_tool": self.physical_tool,
            "mcp_server": self.mcp_server,
            "params": self.params,
            "status": self.status.value,
            "result_summary": self.result_summary,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
        }

