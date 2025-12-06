"""
AuditLogger - 审计日志
记录所有工具调用的完整信息
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import get_logger
from .models import AuditRecord, ToolCallRequest, ToolCallResult, ToolCallStatus

logger = get_logger(__name__)


class AuditLogger:
    """审计日志记录器"""
    
    _instance: Optional["AuditLogger"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, log_dir: Optional[str] = None, max_result_length: int = 500):
        """
        初始化审计日志记录器
        
        Args:
            log_dir: 日志目录，默认为 data/logs/audit
            max_result_length: 结果摘要最大长度
        """
        if self._initialized:
            return
        
        self._initialized = True
        self.max_result_length = max_result_length
        
        # 设置日志目录
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "data" / "logs" / "audit"
        else:
            log_dir = Path(log_dir)
        
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取专用的审计 logger
        self.audit_logger = get_logger("audit")
        
        logger.info(f"AuditLogger 初始化完成，日志目录: {self.log_dir}")
    
    def log_call(self, request: ToolCallRequest, result: ToolCallResult):
        """
        记录工具调用
        
        Args:
            request: 工具调用请求
            result: 工具调用结果
        """
        # 生成结果摘要
        result_summary = self._summarize_result(result.result)
        
        # 创建审计记录
        record = AuditRecord(
            request_id=request.request_id,
            session_id=request.session_id,
            caller_agent=request.caller_agent,
            logical_name=request.logical_name,
            physical_tool=result.physical_tool,
            mcp_server=result.mcp_server,
            params=request.params,
            status=result.status,
            result_summary=result_summary,
            error=result.error,
            start_time=result.start_time,
            end_time=result.end_time,
            duration_ms=result.duration_ms,
        )
        
        # 写入日志
        self._write_log(record)
        
        # 输出到标准日志
        status_emoji = "✅" if result.status == ToolCallStatus.SUCCESS else "❌"
        self.audit_logger.info(
            f"{status_emoji} [{record.request_id}] "
            f"{record.caller_agent} -> {record.logical_name} "
            f"({record.physical_tool}@{record.mcp_server}) "
            f"[{record.duration_ms:.0f}ms]"
        )
    
    def _summarize_result(self, result: Any) -> Optional[str]:
        """生成结果摘要"""
        if result is None:
            return None
        
        if isinstance(result, str):
            summary = result
        else:
            try:
                summary = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                summary = str(result)
        
        # 截断
        if len(summary) > self.max_result_length:
            summary = summary[:self.max_result_length] + "..."
        
        return summary
    
    def _write_log(self, record: AuditRecord):
        """写入日志文件"""
        # 按日期分割日志文件
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date_str}.jsonl"
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"写入审计日志失败: {e}")
    
    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        caller_agent: Optional[str] = None,
        logical_name: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        查询审计日志
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            caller_agent: 调用者 Agent
            logical_name: 逻辑工具名
            session_id: 会话 ID
            limit: 返回条数限制
        
        Returns:
            审计记录列表
        """
        records = []
        
        # 遍历日志文件
        for log_file in sorted(self.log_dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if len(records) >= limit:
                            break
                        
                        record = json.loads(line.strip())
                        
                        # 过滤条件
                        if caller_agent and record.get("caller_agent") != caller_agent:
                            continue
                        if logical_name and record.get("logical_name") != logical_name:
                            continue
                        if session_id and record.get("session_id") != session_id:
                            continue
                        
                        records.append(record)
                
                if len(records) >= limit:
                    break
            except Exception as e:
                logger.warning(f"读取审计日志失败: {log_file}, 错误: {e}")
        
        return records[:limit]

