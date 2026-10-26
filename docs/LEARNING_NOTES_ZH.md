# Agent Service Toolkit 二次开发说明

本仓库基于 [JoshuaC215/agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit)，用于实践 Agent 应用开发与后端服务工程。上游提供 LangGraph、FastAPI、Streamlit、客户端和多个 Agent 示例；本分支集中修改模型兼容、会话与记忆、工具以及接口可靠性。

项目沿用上游 MIT 许可证。这里记录本人在原工程上的改动，区分已完成的实现与框架原有能力。

## 本分支完成的修改

| 内容 | 实现方式 | 主要代码或测试 |
| --- | --- | --- |
| DeepSeek 适配 | 使用 Function Calling 提取结构化信息；关闭思考模式，处理多轮工具调用历史消息不保留 `reasoning_content` 的兼容问题 | `src/core/llm.py`、`src/agents/interrupt_agent.py`、`tests/core/test_llm.py` |
| 切换 Agent 创建新会话 | 切换 Agent 后重置当前会话，生成新的 `thread_id`，避免继续使用另一个 Agent 的对话状态 | `src/streamlit_app.py`、`tests/app/test_streamlit_app.py` |
| SQLite 长期记忆 | 将长期 Store 保存到 SQLite，与 Checkpoint 一样能够跨连接、跨服务重启保留数据 | `src/memory/sqlite.py`、`tests/memory/test_sqlite.py` |
| 时间查询工具 | 增加当前时间工具，并验证 ToolNode 执行和工具结果的 `tool_call_id` 关联 | `src/agents/tools.py`、`tests/agents/test_tools.py` |
| 请求与错误追踪 | 为请求添加 `X-Request-ID`，在 HTTP 错误、参数校验错误及 SSE 错误中携带请求标识；未知 Agent 返回 404 | `src/service/service.py`、`tests/service/test_service.py` |
| 超时与重试 | 将 DeepSeek 调用超时和最大重试次数暴露为配置项 | `src/core/settings.py`、`src/core/llm.py`、`tests/core/test_llm.py` |
| 基础并发限制 | 使用异步信号量限制单进程的 invoke / stream 活跃请求，排队超时返回 429 与 `Retry-After` | `src/service/service.py`、`tests/service/test_concurrency.py` |

## Windows 本地运行

环境：Python 3.13、uv，使用云端 DeepSeek API。以下流程不要求 Docker、WSL 或本地 GPU。

### 获取当前开发分支

```cmd
git clone --branch fix/new-thread-on-agent-change https://github.com/zyh141665/agent-service-toolkit.git
cd agent-service-toolkit
uv sync --frozen
copy .env.example .env
notepad .env
```

如果已经有 `.env`，直接编辑现有文件。将 `.env` 中的对应配置填写为：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DEFAULT_MODEL=deepseek-v4-flash
HOST=127.0.0.1
PORT=8080
AGENT_URL=http://127.0.0.1:8080
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=checkpoints.db
AUTH_SECRET=replace_with_your_own_random_secret
DEEPSEEK_TIMEOUT_SECONDS=60
DEEPSEEK_MAX_RETRIES=2
AGENT_MAX_CONCURRENT_RUNS=8
AGENT_QUEUE_TIMEOUT_SECONDS=5
```

这里的值是示例，API Key 和鉴权密钥需要由使用者自行配置。前后端都从项目根目录启动，读取同一份 `.env`。

### 启动后端

```cmd
uv run python src\run_service.py
```

API 文档：`http://127.0.0.1:8080/docs`。健康检查：

```cmd
curl.exe http://127.0.0.1:8080/health
```

### 启动前端

另开一个 CMD 窗口，切换到同一个项目根目录后执行：

```cmd
uv run streamlit run src\streamlit_app.py
```

打开 `http://127.0.0.1:8501`。首次运行若询问 Email，可以留空并回车。先选择 `chatbot` 验证基本对话，再选择 `interrupt-agent` 体验生日信息提取、人工确认和记忆写入流程。其他 Agent 可能需要额外的服务或凭证。

## 会话与记忆验证

1. 在同一个聊天中提供一条测试信息，再追问，验证当前会话历史。
2. 点击 New Chat，确认新会话不会自动携带上一会话的完整历史。
3. 切换 Agent，确认浏览器地址中的 `thread_id` 更新。
4. 在 `interrupt-agent` 中按提示确认记忆写入，保持同一 `user_id`，新建会话并追问，验证长期 Store。
5. 重启后端，使用相同用户身份及相同数据库，验证已保存的状态与记忆能够恢复。

`thread_id` 标识会话；`user_id` 用于组织用户级长期记忆。更换会话不会修改模型参数，跨会话记住信息依靠数据库读取。这里的 ID 是应用提供的标识，不等同于已实现用户登录或多租户权限校验。

## 测试与代码检查

从仓库根目录执行以下回归测试。测试主要使用 mock 和临时数据库，不需要对真实模型发起请求；它们也不替代人工操作前端的集成验证。

```cmd
uv run --frozen --no-sync pytest tests\core\test_llm.py tests\memory\test_sqlite.py tests\agents\test_tools.py tests\service\test_concurrency.py tests\service\test_service.py tests\service\test_auth.py tests\service\test_service_streaming.py tests\service\test_service_message_generator.py tests\service\test_threads_sqlite.py -q
```

切换 Agent 的前端回归测试：

```cmd
uv run --frozen --no-sync pytest tests\app\test_streamlit_app.py -k agent_change_starts_new_chat -q
```

代码规范检查：

```cmd
uv run --frozen --no-sync ruff check src\agents\interrupt_agent.py src\agents\tools.py src\core\llm.py src\core\settings.py src\memory\sqlite.py src\service\service.py src\streamlit_app.py tests\core\test_llm.py tests\memory\test_sqlite.py tests\agents\test_tools.py tests\service\test_concurrency.py tests\service\conftest.py tests\service\test_service.py tests\app\test_streamlit_app.py
```

若 Windows 的默认临时目录提示拒绝访问，在命令后追加 `--basetemp`，指定一个新的、可写的测试专用目录。pytest 可能清理这个目录，不要使用项目根目录或存放个人文件的目录。

## 范围与限制

- 并发限制作用于单个 Python 进程，多个 worker 或多副本需要共享限流策略；它也不是按用户限流。
- SQLite 用于本地实践，未验证生产规模的数据库吞吐或并发性能。
- `AUTH_SECRET` 为共享 Bearer Token，未实现完整账号系统、用户级授权和租户隔离。
- DeepSeek 的兼容方案选择关闭思考模式，未实现思考模式下 `reasoning_content` 的完整保存与回传。
- 流式响应开始后不能再修改 HTTP 状态码；流内错误通过 SSE 错误事件及请求 ID 反馈。
- `.env`、会话数据库、日志和虚拟环境不作为作品集内容上传。仓库提供 `.env.example` 说明配置。

## 项目来源

- 上游：[JoshuaC215/agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit)
- 本人分支：[fix/new-thread-on-agent-change](https://github.com/zyh141665/agent-service-toolkit/tree/fix/new-thread-on-agent-change)
- 上游基线：`88ebfa1`。使用 `git log 88ebfa1..HEAD --oneline` 查看本分支新增提交，使用 `git diff 88ebfa1..HEAD` 查看修改。
