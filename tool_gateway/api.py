"""
ToolGateway API 路由
提供服务注册、心跳、工具查询等 HTTP 接口
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.logger import get_logger
from .registry import ServerRegistry, ServerStatus

logger = get_logger(__name__)

# 创建路由
router = APIRouter(prefix="/registry", tags=["Server Registry"])


# ============== 请求/响应模型 ==============

class RegisterRequest(BaseModel):
    """注册请求"""
    name: str = Field(..., description="Server 名称")
    description: str = Field("", description="Server 描述")
    environment: str = Field("default", description="环境标识")
    weight: int = Field(100, ge=1, le=1000, description="权重")
    tools: List[str] = Field(default_factory=list, description="提供的工具列表")


class HeartbeatRequest(BaseModel):
    """心跳请求"""
    name: str = Field(..., description="Server 名称")


class DeregisterRequest(BaseModel):
    """注销请求"""
    name: str = Field(..., description="Server 名称")


class ServerInfo(BaseModel):
    """Server 信息"""
    name: str
    description: str
    environment: str
    weight: int
    status: str
    last_heartbeat: Optional[str]
    registered_at: Optional[str]
    tools: List[str]
    stats: dict


class RegistryResponse(BaseModel):
    """通用响应"""
    success: bool
    message: str
    data: Optional[dict] = None


# ============== API 端点 ==============

@router.post("/register", response_model=RegistryResponse)
async def register_server(request: RegisterRequest):
    """
    注册 MCP Server
    
    Server 通过此接口向注册中心注册自己，提供名称、描述、权重和工具列表。
    """
    try:
        registry = ServerRegistry()
        server = registry.register(
            name=request.name,
            description=request.description,
            environment=request.environment,
            weight=request.weight,
            tools=request.tools,
        )
        
        logger.info(f"API: Server 注册成功 - {request.name}")
        return RegistryResponse(
            success=True,
            message=f"Server {request.name} 注册成功",
            data=server.to_dict()
        )
    except Exception as e:
        logger.error(f"API: Server 注册失败 - {request.name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat", response_model=RegistryResponse)
async def heartbeat(request: HeartbeatRequest):
    """
    处理 Server 心跳
    
    Server 定期发送心跳，表明自己仍然存活。
    """
    try:
        registry = ServerRegistry()
        success = registry.heartbeat(request.name)
        
        if success:
            return RegistryResponse(
                success=True,
                message=f"心跳已接收: {request.name}"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"未知的 Server: {request.name}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: 处理心跳失败 - {request.name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deregister", response_model=RegistryResponse)
async def deregister_server(request: DeregisterRequest):
    """
    注销 MCP Server
    
    Server 下线时调用此接口注销自己。
    """
    try:
        registry = ServerRegistry()
        success = registry.deregister(request.name)
        
        if success:
            logger.info(f"API: Server 注销成功 - {request.name}")
            return RegistryResponse(
                success=True,
                message=f"Server {request.name} 已注销"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"未找到 Server: {request.name}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Server 注销失败 - {request.name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers", response_model=List[ServerInfo])
async def list_servers(environment: Optional[str] = None, status: Optional[str] = None):
    """
    列出所有注册的 Server
    
    可以按环境和状态过滤。
    """
    registry = ServerRegistry()
    servers = registry.list_all()
    
    # 过滤
    if environment:
        servers = [s for s in servers if s["environment"] == environment]
    if status:
        servers = [s for s in servers if s["status"] == status]
    
    return servers


@router.get("/servers/{name}", response_model=ServerInfo)
async def get_server(name: str):
    """获取指定 Server 的详细信息"""
    registry = ServerRegistry()
    server = registry.get_server(name)
    
    if not server:
        raise HTTPException(status_code=404, detail=f"未找到 Server: {name}")
    
    return server.to_dict()

