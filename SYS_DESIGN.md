# nanobot 系统设计文档

## 1. 项目概述

**nanobot** 是一个超轻量级个人 AI 助手，仅用约 **4,000 行代码**实现核心智能体功能。它采用模块化架构，支持多聊天频道、多 LLM 提供商，具备完整的工具调用能力和记忆系统。

### 核心设计理念

1. **极简主义**：代码量小、易于理解和修改
2. **模块化**：各组件职责清晰，松耦合设计
3. **可扩展**：支持自定义工具和技能
4. **多频道**：同时支持 Telegram、Discord、WhatsApp、飞书等

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Chat Channels                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Telegram │ │ Discord  │ │ WhatsApp │ │  飞书    │            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Message Bus (消息总线)                       │
│                   解耦频道与 Agent 核心                          │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Core (核心)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Context     │  │  Tool       │  │   Session Manager       │ │
│  │ Builder     │  │  Registry   │  │   (对话历史管理)         │ │
│  │ (上下文构建) │  │  (工具注册)  │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Memory      │  │  Skills     │  │   Subagent Manager      │ │
│  │ Store       │  │  Loader     │  │   (子代理管理)           │ │
│  │ (记忆系统)   │  │  (技能加载)  │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Provider (LLM 提供商)                     │
│         OpenRouter / Anthropic / OpenAI / DeepSeek              │
│         Gemini / 智谱 / 通义千问 / Moonshot / vLLM               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 | 关键文件 |
|------|------|----------|
| **Message Bus** | 消息队列，解耦频道与 Agent | `bus/queue.py`, `bus/events.py` |
| **Agent Loop** | 核心处理引擎，管理 LLM 调用循环 | `agent/loop.py` |
| **Context Builder** | 构建系统提示词和消息上下文 | `agent/context.py` |
| **Tool Registry** | 工具注册和执行管理 | `agent/tools/registry.py` |
| **Channel Manager** | 管理多个聊天频道 | `channels/manager.py` |
| **Session Manager** | 对话历史持久化 | `session/manager.py` |
| **Memory Store** | 短期/长期记忆管理 | `agent/memory.py` |
| **Skills Loader** | 技能加载和渐进式加载 | `agent/skills.py` |

---

## 3. 核心流程详解

### 3.1 消息处理流程

```
用户发送消息
    │
    ▼
┌─────────────────┐
│  Chat Channel   │ ──▶ 权限检查 (is_allowed)
│  (Telegram等)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Message Bus   │ ──▶ publish_inbound()
│   (inbound队列)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Agent Loop    │
│   (run 方法)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ _process_message│
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ 普通消息 │ │系统消息 │
│(用户对话)│ │(子代理) │
└────┬───┘ └────┬───┘
     │          │
     ▼          ▼
┌─────────────────────────┐
│   ContextBuilder        │
│   build_messages()      │ ──▶ 组装系统提示词 + 历史 + 当前消息
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   LLM Provider.chat()   │ ──▶ 调用大模型
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│ 直接回复 │ │ 需要工具调用  │
│(无tool) │ │(has_tool_calls)│
└────┬───┘ └──────┬───────┘
     │            │
     │            ▼
     │     ┌─────────────────┐
     │     │ ToolRegistry    │
     │     │ execute()       │ ──▶ 执行工具
     │     └────────┬────────┘
     │              │
     │              ▼
     │     ┌─────────────────┐
     │     │  工具执行结果    │ ──▶ 添加回 messages
     │     │  add_tool_result │
     │     └────────┬────────┘
     │              │
     └──────────────┘
              │
              ▼ (循环，直到 max_iterations 或无工具调用)
┌─────────────────────────┐
│   保存到 Session        │
│   (对话历史持久化)       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Message Bus           │
│   publish_outbound()    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Channel 发送给用户     │
└─────────────────────────┘
```

### 3.2 Agent Loop 核心逻辑

```python
# agent/loop.py 核心流程

async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
    # 1. 获取或创建会话
    session = self.sessions.get_or_create(msg.session_key)
    
    # 2. 更新工具上下文（channel/chat_id）
    self._update_tool_contexts(msg.channel, msg.chat_id)
    
    # 3. 构建消息列表（系统提示词 + 历史 + 当前消息）
    messages = self.context.build_messages(
        history=session.get_history(),
        current_message=msg.content,
        media=msg.media,
        channel=msg.channel,
        chat_id=msg.chat_id,
    )
    
    # 4. Agent 循环（最多 max_iterations 次）
    while iteration < self.max_iterations:
        iteration += 1
        
        # 4.1 调用 LLM
        response = await self.provider.chat(
            messages=messages,
            tools=self.tools.get_definitions(),
            model=self.model
        )
        
        # 4.2 处理工具调用
        if response.has_tool_calls:
            # 添加助手消息（包含工具调用）
            messages = self.context.add_assistant_message(...)
            
            # 执行每个工具调用
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages = self.context.add_tool_result(messages, ...)
        else:
            # 无工具调用，完成
            final_content = response.content
            break
    
    # 5. 保存会话历史
    session.add_message("user", msg.content)
    session.add_message("assistant", final_content)
    self.sessions.save(session)
    
    # 6. 返回响应
    return OutboundMessage(...)
```

---

## 4. 工具系统 (Tool System)

### 4.1 工具基类设计

所有工具继承自 `Tool` 基类，实现标准接口：

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...           # 工具名称
    
    @property  
    @abstractmethod
    def description(self) -> str: ...    # 功能描述
    
    @property
    @abstractmethod
    def parameters(self) -> dict: ...    # JSON Schema 参数定义
    
    @abstractmethod
    async def execute(self, **kwargs) -> str: ...  # 执行逻辑
```

### 4.2 内置工具列表

| 工具 | 名称 | 功能 | 安全特性 |
|------|------|------|----------|
| **read_file** | 文件读取 | 读取文件内容 | 可选目录限制 |
| **write_file** | 文件写入 | 写入/创建文件 | 可选目录限制 |
| **edit_file** | 文件编辑 | 文本替换编辑 | 可选目录限制 |
| **list_dir** | 目录列表 | 列出目录内容 | 可选目录限制 |
| **exec** | 命令执行 | 执行 shell 命令 | 危险命令拦截、超时控制 |
| **web_search** | 网络搜索 | Brave Search API | API Key 验证 |
| **web_fetch** | 网页获取 | 抓取并提取内容 | URL 验证、重定向限制 |
| **message** | 消息发送 | 向用户发送消息 | 上下文绑定 |
| **spawn** | 子代理 | 创建后台任务 | 隔离执行环境 |
| **cron** | 定时任务 | 添加/管理定时任务 | 会话上下文绑定 |

### 4.3 工具注册与执行

```python
# ToolRegistry 管理所有工具
class ToolRegistry:
    def register(self, tool: Tool) -> None      # 注册工具
    def get_definitions(self) -> list[dict]     # 获取 OpenAI 格式定义
    async def execute(self, name, params) -> str # 执行工具（带验证）
```

---

## 5. 上下文构建系统 (Context Builder)

### 5.1 系统提示词组装

```
┌─────────────────────────────────────────┐
│         System Prompt 组装流程           │
├─────────────────────────────────────────┤
│ 1. Core Identity (核心身份)              │
│    - nanobot 介绍、能力说明              │
│    - 当前时间、运行时信息                │
│    - Workspace 路径                      │
├─────────────────────────────────────────┤
│ 2. Bootstrap Files (启动文件)            │
│    - AGENTS.md    (代理配置)             │
│    - SOUL.md      (个性设定)             │
│    - USER.md      (用户信息)             │
│    - TOOLS.md     (工具说明)             │
│    - IDENTITY.md  (身份扩展)             │
├─────────────────────────────────────────┤
│ 3. Memory (记忆)                         │
│    - Long-term Memory (MEMORY.md)        │
│    - Today's Notes (YYYY-MM-DD.md)       │
├─────────────────────────────────────────┤
│ 4. Always-loaded Skills (常驻技能)       │
│    - 完整技能内容加载到上下文            │
├─────────────────────────────────────────┤
│ 5. Available Skills Summary (可用技能)   │
│    - XML 格式摘要                        │
│    - 渐进式加载（需要时 read_file）      │
└─────────────────────────────────────────┘
```

### 5.2 渐进式技能加载

为控制上下文长度，采用**渐进式加载**策略：

1. **常驻技能 (Always Skills)**：始终加载完整内容
2. **可用技能摘要**：仅加载名称、描述、路径
3. **按需加载**：Agent 使用 `read_file` 读取需要的技能

---

## 6. 记忆系统 (Memory System)

### 6.1 记忆类型

```
┌─────────────────────────────────────────┐
│           MemoryStore                   │
├─────────────────────────────────────────┤
│  Long-term Memory                       │
│  ├── MEMORY.md                          │
│  └── 持久化长期记忆                      │
├─────────────────────────────────────────┤
│  Daily Notes (每日笔记)                  │
│  ├── 2026-02-07.md                      │
│  ├── 2026-02-06.md                      │
│  └── 按日期组织的短期记忆                │
├─────────────────────────────────────────┤
│  Session History (会话历史)              │
│  ├── telegram:123456.jsonl              │
│  ├── discord:789012.jsonl               │
│  └── 按频道+用户隔离的对话历史            │
└─────────────────────────────────────────┘
```

### 6.2 记忆使用场景

| 场景 | 存储位置 | 更新方式 |
|------|----------|----------|
| 用户偏好 | MEMORY.md | Agent 主动写入 |
| 今日任务/笔记 | YYYY-MM-DD.md | Agent 主动追加 |
| 对话历史 | sessions/*.jsonl | 自动保存 |
| 近期回顾 | 最近 N 天笔记 | 自动读取 |

---

## 7. 频道系统 (Channel System)

### 7.1 频道架构

```
┌─────────────────────────────────────────┐
│           BaseChannel (抽象基类)         │
│  - start() / stop()                     │
│  - send()                               │
│  - is_allowed() 权限检查                 │
│  - _handle_message() 消息处理            │
└─────────────────────────────────────────┘
           │
    ┌──────┼──────┬────────┐
    ▼      ▼      ▼        ▼
┌────────┐┌─────┐┌────────┐┌────────┐
│Telegram││Discord││WhatsApp││ 飞书   │
│Channel ││Channel││Channel ││Channel │
└────────┘└─────┘└────────┘└────────┘
```

### 7.2 频道特性

| 频道 | 协议 | 媒体支持 | 特殊功能 |
|------|------|----------|----------|
| **Telegram** | HTTP Long Polling | 文本、图片、语音、文档 | Markdown 转 HTML |
| **Discord** | WebSocket Gateway | 文本、图片 | 意图(Intent)管理 |
| **WhatsApp** | WebSocket (bridge) | 文本、图片、语音 | 需配合 bridge 服务 |
| **飞书** | WebSocket | 文本、图片 | 事件订阅、加密验证 |

### 7.3 消息总线 (Message Bus)

```python
class MessageBus:
    inbound: asyncio.Queue[InboundMessage]   # 频道 → Agent
    outbound: asyncio.Queue[OutboundMessage] # Agent → 频道
    
    async def publish_inbound(msg)   # 频道调用
    async def consume_inbound()      # Agent 循环调用
    async def publish_outbound(msg)  # Agent 调用
    async def dispatch_outbound()    # 分发到对应频道
```

---

## 8. 子代理系统 (Subagent)

### 8.1 设计目的

- **后台执行**：耗时任务不阻塞主对话
- **任务隔离**：独立上下文，避免干扰
- **结果通知**：完成后主动通知用户

### 8.2 子代理执行流程

```
用户请求创建子代理
    │
    ▼
┌─────────────────┐
│   spawn 工具     │
│  (SpawnTool)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SubagentManager │
│    spawn()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ asyncio.create  │────▶│ _run_subagent() │
│    _task()      │     │  (后台执行)      │
└─────────────────┘     └─────────────────┘
                                  │
                                  ▼
                        ┌─────────────────┐
                        │ 简化版 Agent Loop │
                        │ (无 message/spawn) │
                        └─────────────────┘
                                  │
                                  ▼
                        ┌─────────────────┐
                        │  完成后发送系统消息 │
                        │  (channel:system) │
                        └─────────────────┘
```

### 8.3 子代理限制

- **无 message 工具**：不能直接发送消息
- **无 spawn 工具**：不能创建嵌套子代理
- **简化工具集**：仅文件、命令、网络搜索
- **有限迭代**：最多 15 次迭代

---

## 9. 定时任务系统 (Cron Service)

### 9.1 功能特性

- **多种调度方式**：固定时间、间隔执行、Cron 表达式
- **持久化存储**：任务保存到磁盘，重启不丢失
- **消息投递**：支持将结果发送到指定频道

### 9.2 任务类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `at` | 指定时间执行一次 | 2026-02-08 09:00 |
| `every` | 每隔 N 秒执行 | 每 3600 秒 |
| `cron` | Cron 表达式 | `0 9 * * *` (每天9点) |

---

## 10. 配置系统

### 10.1 配置层级

```
┌─────────────────────────────────────────┐
│  环境变量 (NANOBOT_* )                  │
│  最高优先级                              │
├─────────────────────────────────────────┤
│  ~/.nanobot/config.json                 │
│  用户配置文件                            │
├─────────────────────────────────────────┤
│  默认值 (Config 类)                      │
│  最低优先级                              │
└─────────────────────────────────────────┘
```

### 10.2 配置结构

```python
class Config:
    agents: AgentsConfig      # 代理默认配置
    channels: ChannelsConfig  # 频道配置
    providers: ProvidersConfig # LLM 提供商配置
    gateway: GatewayConfig    # 网关配置
    tools: ToolsConfig        # 工具配置
```

### 10.3 支持的 LLM 提供商

| 提供商 | 标识 | 特点 |
|--------|------|------|
| OpenRouter | `openrouter/*` | 聚合多模型，推荐 |
| Anthropic | `anthropic/*` | Claude 系列 |
| OpenAI | `openai/*` | GPT 系列 |
| DeepSeek | `deepseek/*` | 国产模型 |
| 智谱/Z.ai | `zai/*` | GLM 系列 |
| 通义千问 | `dashscope/*` | 阿里模型 |
| Moonshot | `moonshot/*` | Kimi 系列 |
| Gemini | `gemini/*` | Google 模型 |
| vLLM | `hosted_vllm/*` | 本地部署 |

---

## 11. 安全设计

### 11.1 命令执行安全 (ExecTool)

```python
# 危险命令拦截模式
DENY_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",      # rm -rf
    r"\b(format|mkq|diskpart)\b", # 磁盘操作
    r"\bdd\s+if=",                # dd 命令
    r">\s*/dev/sd",               # 写入磁盘
    r"\b(shutdown|reboot)\b",     # 系统电源
    r":\(\)\s*\{.*\};\s*:",       # fork bomb
]

# 可选：限制在工作目录内
restrict_to_workspace: bool
```

### 11.2 文件系统安全

- `allowed_dir` 参数限制可访问目录
- 路径解析使用 `resolve()` 防止遍历
- 支持 `restrict_to_workspace` 全局限制

### 11.3 频道访问控制

```python
def is_allowed(sender_id: str) -> bool:
    # allow_from 列表为空时允许所有人
    # 否则仅允许列表中的用户
```

---

## 12. 扩展点

### 12.1 添加新工具

1. 继承 `Tool` 基类
2. 实现 `name`, `description`, `parameters`, `execute`
3. 在 `AgentLoop._register_default_tools()` 中注册

### 12.2 添加新频道

1. 继承 `BaseChannel`
2. 实现 `start()`, `stop()`, `send()`
3. 在 `ChannelManager._init_channels()` 中初始化

### 12.3 添加新技能

1. 在 `workspace/skills/{skill-name}/SKILL.md` 创建技能文件
2. 使用 YAML frontmatter 定义元数据
3. 编写技能说明文档

---

## 13. 代码统计

| 模块 | 文件数 | 核心代码行数 |
|------|--------|--------------|
| agent | 11 | ~1,200 |
| channels | 6 | ~800 |
| bus | 2 | ~120 |
| config | 2 | ~250 |
| providers | 2 | ~200 |
| session | 1 | ~150 |
| cron | 3 | ~300 |
| utils | 2 | ~100 |
| **总计** | **~30** | **~3,400** |

---

*文档生成时间: 2026-02-07*
