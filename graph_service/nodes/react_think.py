"""
ReAct Think Node
思考节点：LLM 观察当前状态并决定下一步行动
"""
from typing import Dict, Any
from loguru import logger
from ..state import GraphState
from langchain_community.llms import Ollama
from utils import get_config_manager, load_agent_config
import re
import json


def get_llm():
    """获取或创建 LLM 实例（使用配置管理器）"""
    config_manager = get_config_manager()
    return config_manager.get_llm("react_think")


def _get_agent_config(target_agent: str) -> Dict[str, Any]:
    """
    获取 Agent 配置

    Args:
        target_agent: 目标 Agent 名称（如 "network_agent", "database_agent"）

    Returns:
        Agent 配置字典，包含 system_prompt、tools_prefix 等
    """
    from utils import load_agent_mapping_config

    # 加载 Agent 映射配置
    mapping_config = load_agent_mapping_config()
    agents_mapping = mapping_config.get("agents", {})

    # 查找对应的 config_key
    config_key = None
    for agent_info in agents_mapping.values():
        if agent_info.get("full_name") == target_agent:
            config_key = agent_info.get("config_key")
            break

    if not config_key:
        logger.warning(f"未找到 Agent {target_agent} 的映射配置，使用默认配置")
        return {}

    # 加载 Agent 配置
    agent_config = load_agent_config()
    agents = agent_config.get("agents", {})

    return agents.get(config_key, {})


def build_think_prompt(state: GraphState, available_tools: list) -> str:
    """
    构建思考 Prompt

    Args:
        state: 当前状态
        available_tools: 可用工具列表

    Returns:
        Prompt 字符串
    """
    # 获取当前 Agent 的配置
    target_agent = state.get("target_agent", "network_agent")
    agent_config = _get_agent_config(target_agent)

    # 获取 system_prompt（如果没有配置，使用默认值）
    system_prompt = agent_config.get("system_prompt", "你是一个有用的AI助手。请分析用户问题并决定下一步行动。")

    # 获取当前任务描述（优先使用 agent_plan 中的任务描述）
    user_query = state['user_query']
    agent_plan = state.get("agent_plan")
    current_agent_index = state.get("current_agent_index", 0)

    if agent_plan and current_agent_index < len(agent_plan):
        # 使用 agent_plan 中的任务描述
        task_desc = agent_plan[current_agent_index].get("task", user_query)
        user_query = task_desc

    # 工具列表
    tools_desc = "\n".join([
        f"- {tool['name']}: {tool['description']}"
        for tool in available_tools
    ])

    # 执行历史
    history_desc = ""
    if state.get("execution_history"):
        history_desc = "\n\n执行历史:\n"
        for i, record in enumerate(state["execution_history"], 1):
            history_desc += f"\n步骤 {i}:\n"
            history_desc += f"  思考: {record.get('thought', 'N/A')}\n"
            history_desc += f"  行动: {record.get('action', 'N/A')}\n"
            history_desc += f"  观察: {record.get('observation', 'N/A')[:200]}...\n"

    # 上一步观察
    last_obs = state.get("last_observation", "")
    last_obs_desc = f"\n\n上一步观察结果:\n{last_obs}\n" if last_obs else ""

    # 构建完整 prompt
    prompt = f"""{system_prompt}

用户问题: {user_query}

可用工具:
{tools_desc}
{history_desc}{last_obs_desc}

请按照以下格式输出:

THOUGHT: [你的思考过程，分析当前情况和需要做什么]
ACTION: [TOOL 或 FINISH]
TOOL: [如果 ACTION 是 TOOL，写工具名称，如 network.ping]
PARAMS: [如果 ACTION 是 TOOL，写 JSON 格式的参数，如 {{"target": "baidu.com", "count": 4}}]

重要提示:
1. 如果需要使用前面步骤的结果（如 IP 地址），请从"上一步观察结果"中提取
2. 例如：如果上一步查询到 IP 是 109.244.5.94，下一步 mtr 应该使用这个 IP，而不是域名
3. 如果任务已完成，ACTION 设为 FINISH
4. 每次只执行一个工具
5. PARAMS 必须是有效的 JSON 格式

现在请开始分析并输出你的决策:"""

    return prompt


def parse_llm_output(output: str, tools_prefix: str = None) -> Dict[str, Any]:
    """
    解析 LLM 输出

    支持两种格式：
    1. 纯文本格式：THOUGHT: ... ACTION: ... TOOL: ... PARAMS: ...
    2. JSON 格式：{"THOUGHT": "...", "ACTION": "...", "TOOL": "...", "PARAMS": {...}}

    Args:
        output: LLM 输出字符串
        tools_prefix: 工具前缀（如 "network"、"mysql"），用于自动补全工具名称

    Returns:
        解析后的字典
    """
    result = {
        "thought": "",
        "action_type": "FINISH",
        "tool_name": None,
        "params": {}
    }

    # 尝试解析 JSON 格式
    # 提取 JSON 代码块（可能包含 ```json 标记）
    json_match = re.search(r'```json\s*(\{.+?\})\s*```', output, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            json_data = json.loads(json_match.group(1))
            result["thought"] = json_data.get("THOUGHT", "")
            action = json_data.get("ACTION", "FINISH")
            if action.upper() == "FINISH":
                result["action_type"] = "FINISH"
            elif action.upper() == "TOOL":
                result["action_type"] = "TOOL"
                result["tool_name"] = json_data.get("TOOL")
                result["params"] = json_data.get("PARAMS", {})
            else:
                # 直接写了工具名
                result["action_type"] = "TOOL"
                result["tool_name"] = action
                result["params"] = json_data.get("PARAMS", {})

            # 自动补全工具名称前缀
            if result["tool_name"] and tools_prefix:
                result["tool_name"] = _ensure_tool_prefix(result["tool_name"], tools_prefix)

            return result
        except json.JSONDecodeError as e:
            logger.warning(f"解析 JSON 格式失败: {e}")
            # 继续尝试纯文本格式

    # 纯文本格式解析
    # 提取 THOUGHT
    thought_match = re.search(r'THOUGHT:\s*(.+?)(?=\nACTION:|\nTOOL:|\n\n|$)', output, re.DOTALL | re.IGNORECASE)
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # 提取 ACTION
    # 支持两种格式：
    # 1. ACTION: TOOL 或 ACTION: FINISH
    # 2. ACTION: tool_name（直接写工具名）
    action_match = re.search(r'ACTION:\s*(TOOL|FINISH|[a-zA-Z_][a-zA-Z0-9_.]*)', output, re.IGNORECASE)
    if action_match:
        action_value = action_match.group(1).strip()
        if action_value.upper() == "FINISH":
            result["action_type"] = "FINISH"
        elif action_value.upper() == "TOOL":
            result["action_type"] = "TOOL"
        else:
            # 直接写了工具名，如 ACTION: mysql.list_tables
            result["action_type"] = "TOOL"
            result["tool_name"] = action_value

    # 如果 ACTION 是 TOOL，提取工具名和参数
    if result["action_type"] == "TOOL":
        # 如果还没有提取到工具名，从 TOOL: 行提取
        if not result["tool_name"]:
            tool_match = re.search(r'TOOL:\s*([^\n]+)', output, re.IGNORECASE)
            if tool_match:
                result["tool_name"] = tool_match.group(1).strip()

        # 提取 PARAMS
        params_match = re.search(r'PARAMS:\s*(\{.+?\})', output, re.DOTALL | re.IGNORECASE)
        if params_match:
            try:
                result["params"] = json.loads(params_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"解析参数 JSON 失败: {e}, 原始内容: {params_match.group(1)}")
                result["params"] = {}

        # 自动补全工具名称前缀
        if result["tool_name"] and tools_prefix:
            result["tool_name"] = _ensure_tool_prefix(result["tool_name"], tools_prefix)

    return result


def _ensure_tool_prefix(tool_name: str, tools_prefix: str) -> str:
    """
    确保工具名称包含前缀

    如果工具名称已经包含前缀（如 "mysql.list_tables"），则不做修改
    如果工具名称没有前缀（如 "list_tables"），则自动添加前缀（变成 "mysql.list_tables"）

    Args:
        tool_name: 工具名称
        tools_prefix: 工具前缀（如 "network"、"mysql"）

    Returns:
        包含前缀的工具名称
    """
    if not tool_name or not tools_prefix:
        return tool_name

    # 如果工具名称已经包含前缀，直接返回
    if tool_name.startswith(tools_prefix + "."):
        return tool_name

    # 如果工具名称包含其他前缀（如 "network.ping"），也直接返回
    if "." in tool_name:
        return tool_name

    # 否则，自动添加前缀
    full_tool_name = f"{tools_prefix}.{tool_name}"
    logger.info(f"自动补全工具名称: {tool_name} -> {full_tool_name}")
    return full_tool_name


async def react_think_node(state: GraphState) -> GraphState:
    """
    ReAct 思考节点

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    state["current_node"] = "react_think"

    try:
        # 检查是否达到最大迭代次数
        if state["current_step"] >= state["max_iterations"]:
            logger.warning(f"达到最大迭代次数: {state['max_iterations']}")
            state["is_finished"] = True
            state["next_action"] = {
                "action_type": "FINISH",
                "tool_name": None,
                "params": {}
            }
            return state

        # 获取可用工具列表
        from mcp_manager import McpClientManager
        from utils import load_tools_config

        tools_config = load_tools_config()

        # 根据 target_agent 决定使用哪些工具
        target_agent = state.get("target_agent", "network_agent")
        agent_config = _get_agent_config(target_agent)

        # 从 agent_config 获取 tools_prefix
        tools_prefix = agent_config.get("tools_prefix", "network")

        available_tools = []
        prefix_tools = tools_config.get("tools", {}).get(tools_prefix, {})
        for tool_key, tool_config in prefix_tools.items():
            available_tools.append({
                "name": tool_config["name"],
                "description": tool_config["description"]
            })

        # 构建 Prompt
        prompt = build_think_prompt(state, available_tools)

        # 调用 LLM
        logger.info(f"ReAct Think - 步骤 {state['current_step']}")
        llm = get_llm()
        llm_output = llm.invoke(prompt)

        logger.info(f"LLM 输出:\n{llm_output[:500]}...")

        # 解析 LLM 输出（传递 tools_prefix 用于自动补全工具名称）
        parsed = parse_llm_output(llm_output, tools_prefix=tools_prefix)

        logger.info(f"解析结果: action_type={parsed['action_type']}, tool={parsed.get('tool_name')}")

        # 保存决策
        state["next_action"] = {
            "action_type": parsed["action_type"],
            "tool_name": parsed.get("tool_name"),
            "params": parsed.get("params", {}),
            "thought": parsed.get("thought", "")
        }

        # 如果决定 FINISH，标记为完成
        if parsed["action_type"] == "FINISH":
            state["is_finished"] = True
            logger.info("LLM 决定完成任务")

    except Exception as e:
        error_msg = f"ReAct Think 失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append(error_msg)
        state["is_finished"] = True
        state["next_action"] = {
            "action_type": "FINISH",
            "tool_name": None,
            "params": {}
        }

    return state

