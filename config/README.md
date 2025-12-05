# 配置文件说明

## 📁 配置文件结构

```
config/
├── README.md                    # 本文件
├── agent_config.yaml            # Agent 配置（system_prompt、工具前缀等）
├── agent_mapping.yaml           # Agent 映射关系（短名称、完整名称等）
├── llm_config.yaml              # LLM 配置（模型、温度、超时等）
├── tools_config.yaml            # 工具配置（工具参数、描述等）
├── mcp_config.yaml              # MCP Server 配置
├── langchain_config.yaml        # LangChain 配置
├── langgraph_config.yaml        # LangGraph 工作流配置
├── router_prompt.yaml           # Router Prompt 配置
└── workflow_templates.yaml      # 工作流模板配置
```

## 🎯 配置管理原则

### **1. 配置分层**

- **`.env` 文件**：只包含基础设施配置
  - 服务地址和端口（如 `OLLAMA_BASE_URL`、`GRAPH_SERVICE_PORT`）
  - 数据库连接信息（如 `MYSQL_HOST`、`MYSQL_PASSWORD`）
  - 日志配置（如 `LOG_LEVEL`、`LOG_FILE`）
  - 外部服务 URL（如 `OPENWEBUI_URL`）

- **`config/*.yaml` 文件**：包含业务逻辑配置
  - LLM 模型选择、参数（如 `model`、`temperature`）
  - Agent 配置（如 `system_prompt`、`tools_prefix`）
  - 工具配置（如工具参数、描述）
  - 工作流配置（如节点、边、路由规则）

### **2. 优先级规则**

**配置文件（YAML）优先级 > 环境变量（.env）优先级**

- 所有业务逻辑配置都应该在 YAML 文件中定义
- YAML 文件可以通过 `${VAR_NAME}` 语法引用环境变量
- 如果环境变量不存在，使用 YAML 中的默认值

**示例**：

```yaml
# config/llm_config.yaml
llm:
  base_url: "${OLLAMA_BASE_URL}"  # 从 .env 读取
  model: "gpt-oss:20b"             # 直接在 YAML 中定义
```

### **3. 配置热加载**

- 所有 `config/*.yaml` 文件支持热加载
- 修改配置文件后，系统会自动检测并重新加载
- 无需重启服务即可应用新配置

## 📝 配置文件详解

### **llm_config.yaml** - LLM 配置

```yaml
llm:
  provider: "ollama"                    # LLM 提供商
  base_url: "${OLLAMA_BASE_URL}"        # Ollama 服务地址（从 .env 读取）
  model: "gpt-oss:20b"                  # 模型名称
  temperature: 0.7                      # 温度参数
  max_tokens: 8000                      # 最大 token 数
  timeout: 120                          # 超时时间（秒）

embedding:
  provider: "ollama"                    # Embedding 提供商
  base_url: "${OLLAMA_BASE_URL}"        # Ollama 服务地址
  model: "nomic-embed-text"             # Embedding 模型
```

**注意**：
- ✅ 所有 LLM 相关配置都在此文件中
- ❌ 不要在 `.env` 中定义 `OLLAMA_MODEL` 等变量

### **agent_config.yaml** - Agent 配置

定义每个 Agent 的 system_prompt、工具前缀等。

```yaml
agents:
  network_diag:
    name: "NetworkDiagAgent"
    description: "网络故障诊断专家"
    tools_prefix: "network"
    system_prompt: |
      你是一个网络诊断专家...
```

### **agent_mapping.yaml** - Agent 映射关系

定义 Agent 的短名称、完整名称、配置键之间的映射关系。

```yaml
agents:
  network:
    config_key: "network_diag"          # agent_config.yaml 中的键
    full_name: "network_agent"          # 在 state 和路由中使用的完整名称
    short_names:                        # 用户可以使用的短名称
      - "network"
      - "net"
    tools_prefix: "network"             # tools_config.yaml 中的工具前缀
```

### **tools_config.yaml** - 工具配置

定义所有工具的参数、描述等。

```yaml
tools:
  network:
    ping:
      name: "network.ping"
      description: "Ping 测试"
      parameters:
        - name: "target"
          type: "string"
          required: true
```

## 🔧 如何添加新配置

### **添加新的 LLM 模型**

1. 修改 `config/llm_config.yaml`：
   ```yaml
   llm:
     model: "new-model:latest"
   ```

2. 无需重启服务，配置会自动热加载

### **添加新的 Agent**

1. 在 `config/agent_config.yaml` 中添加 Agent 配置
2. 在 `config/agent_mapping.yaml` 中添加映射关系
3. 创建 Agent 节点函数（如 `graph_service/nodes/new_agent.py`）
4. 在 `graph_service/graph.py` 中注册节点

## ⚠️ 常见错误

### ❌ 错误：在 `.env` 中定义 LLM 配置

```bash
# .env
OLLAMA_MODEL=deepseek-r1:8b  # ❌ 错误！不会被使用
```

### ✅ 正确：在 `llm_config.yaml` 中定义

```yaml
# config/llm_config.yaml
llm:
  model: "deepseek-r1:8b"  # ✅ 正确！
```

### ❌ 错误：硬编码配置值

```python
# ❌ 错误
llm = Ollama(model="deepseek-r1:8b")
```

### ✅ 正确：从配置文件读取

```python
# ✅ 正确
config_manager = get_config_manager()
llm = config_manager.get_llm()
```

## 📚 参考资料

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [YAML 语法](https://yaml.org/)
- [环境变量最佳实践](https://12factor.net/config)

