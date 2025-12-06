"""
工具结果摘要提取器
用于智能截断和结构化提取工具执行结果的关键信息
"""
import json
import re
from typing import Dict, Any, Optional
from loguru import logger


# 配置：不同类型的截断长度
TRUNCATION_CONFIG = {
    "default": {
        "max_length": 1500,      # 默认最大长度
        "head_length": 600,      # 保留开头的长度
        "tail_length": 600,      # 保留结尾的长度
    },
    "network": {
        "max_length": 1200,
        "head_length": 400,
        "tail_length": 600,      # 网络工具的统计信息通常在结尾
    },
    "database": {
        "max_length": 2000,
        "head_length": 800,
        "tail_length": 800,
    },
}


def smart_truncate(text: str, tool_type: str = "default") -> str:
    """
    智能截断文本，保留开头和结尾
    
    Args:
        text: 原始文本
        tool_type: 工具类型 (network, database, default)
        
    Returns:
        截断后的文本
    """
    if not text:
        return ""
    
    config = TRUNCATION_CONFIG.get(tool_type, TRUNCATION_CONFIG["default"])
    max_length = config["max_length"]
    head_length = config["head_length"]
    tail_length = config["tail_length"]
    
    if len(text) <= max_length:
        return text
    
    # 智能截断：保留开头和结尾
    head = text[:head_length]
    tail = text[-tail_length:]
    
    truncated_chars = len(text) - head_length - tail_length
    separator = f"\n\n... [已省略 {truncated_chars} 字符] ...\n\n"
    
    return head + separator + tail


def get_tool_type(tool_name: str) -> str:
    """根据工具名称获取工具类型"""
    if tool_name.startswith("network.") or tool_name in ["ping", "traceroute", "mtr", "nslookup"]:
        return "network"
    elif tool_name.startswith("mysql.") or "sql" in tool_name.lower() or "database" in tool_name.lower():
        return "database"
    return "default"


def extract_ping_summary(result: Dict[str, Any]) -> str:
    """提取 ping 结果的摘要"""
    try:
        target = result.get("target", "N/A")
        count = result.get("count", "N/A")
        success = result.get("success", False)
        raw_output = result.get("raw_output", "")
        
        # 提取统计信息
        stats = ""
        if raw_output:
            # 匹配 packet loss
            loss_match = re.search(r'(\d+(?:\.\d+)?%)\s*packet loss', raw_output)
            packet_loss = loss_match.group(1) if loss_match else "N/A"
            
            # 匹配 RTT 统计
            rtt_match = re.search(r'rtt\s+min/avg/max[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)', raw_output)
            if rtt_match:
                stats = f"丢包率: {packet_loss}, RTT: min={rtt_match.group(1)}ms, avg={rtt_match.group(2)}ms, max={rtt_match.group(3)}ms"
            else:
                stats = f"丢包率: {packet_loss}"
        
        status = "✅ 成功" if success else "❌ 失败"
        summary = f"[Ping] 目标: {target}, 发包数: {count}, {status}"
        if stats:
            summary += f"\n统计: {stats}"
        
        return summary
    except Exception as e:
        logger.debug(f"提取 ping 摘要失败: {e}")
        return ""


def extract_database_summary(result: Dict[str, Any]) -> str:
    """提取数据库查询结果的摘要"""
    try:
        if isinstance(result, list):
            row_count = len(result)
            if row_count == 0:
                return "[数据库] 查询结果: 0 条记录"
            elif row_count <= 5:
                return f"[数据库] 查询结果: {row_count} 条记录"
            else:
                return f"[数据库] 查询结果: {row_count} 条记录 (仅显示部分)"
        elif isinstance(result, dict):
            if "rows" in result:
                row_count = len(result.get("rows", []))
                return f"[数据库] 查询结果: {row_count} 条记录"
        return "[数据库] 查询完成"
    except Exception as e:
        logger.debug(f"提取数据库摘要失败: {e}")
        return ""


def extract_result_summary(tool_name: str, observation: str) -> Optional[str]:
    """
    从观察结果中提取结构化摘要
    
    Args:
        tool_name: 工具名称
        observation: 完整的观察结果
        
    Returns:
        结构化摘要，如果无法提取则返回 None
    """
    try:
        # 尝试解析 JSON 结果
        if "结果:" in observation:
            json_str = observation.split("结果:")[1].strip()
            result = json.loads(json_str)
            
            # 根据工具类型提取摘要
            if "ping" in tool_name.lower():
                return extract_ping_summary(result)
            elif "mysql" in tool_name.lower() or "sql" in tool_name.lower():
                return extract_database_summary(result)
        
        return None
    except Exception as e:
        logger.debug(f"提取结果摘要失败: {e}")
        return None

