"""使用 Pydantic 的配置模式定义。"""

from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp 频道配置。"""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # 允许的电话号码


class TelegramConfig(BaseModel):
    """Telegram 频道配置。"""
    enabled: bool = False
    token: str = ""  # 从 @BotFather 获取的机器人令牌
    allow_from: list[str] = Field(default_factory=list)  # 允许的用户 ID 或用户名
    proxy: str | None = None  # HTTP/SOCKS5 代理 URL，例如 "http://127.0.0.1:7890" 或 "socks5://127.0.0.1:1080"


class FeishuConfig(BaseModel):
    """飞书/Lark 频道配置，使用 WebSocket 长连接。"""
    enabled: bool = False
    app_id: str = ""  # 从飞书开放平台获取的 App ID
    app_secret: str = ""  # 从飞书开放平台获取的 App Secret
    encrypt_key: str = ""  # 事件订阅的加密密钥（可选）
    verification_token: str = ""  # 事件订阅的验证令牌（可选）
    allow_from: list[str] = Field(default_factory=list)  # 允许的用户 open_id


class DiscordConfig(BaseModel):
    """Discord 频道配置。"""
    enabled: bool = False
    token: str = ""  # 从 Discord 开发者门户获取的机器人令牌
    allow_from: list[str] = Field(default_factory=list)  # 允许的用户 ID
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class ChannelsConfig(BaseModel):
    """聊天频道配置。"""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)


class AgentDefaults(BaseModel):
    """代理默认配置。"""
    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """代理配置。"""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM 提供商配置。"""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """LLM 提供商配置。"""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)


class GatewayConfig(BaseModel):
    """网关/服务器配置。"""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """网页搜索工具配置。"""
    api_key: str = ""  # Brave Search API 密钥
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web 工具配置。"""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell 执行工具配置。"""
    timeout: int = 60


class ToolsConfig(BaseModel):
    """工具配置。"""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # 如果为 true，限制所有工具访问工作区目录


class Config(BaseSettings):
    """nanobot 的根配置。"""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    
    @property
    def workspace_path(self) -> Path:
        """获取展开后的工作区路径。"""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def _match_provider(self, model: str | None = None) -> ProviderConfig | None:
        """根据模型名称匹配提供商。"""
        model = (model or self.agents.defaults.model).lower()
        # 关键词到提供商配置的映射
        providers = {
            "openrouter": self.providers.openrouter,
            "deepseek": self.providers.deepseek,
            "anthropic": self.providers.anthropic,
            "claude": self.providers.anthropic,
            "openai": self.providers.openai,
            "gpt": self.providers.openai,
            "gemini": self.providers.gemini,
            "zhipu": self.providers.zhipu,
            "glm": self.providers.zhipu,
            "zai": self.providers.zhipu,
            "dashscope": self.providers.dashscope,
            "qwen": self.providers.dashscope,
            "groq": self.providers.groq,
            "moonshot": self.providers.moonshot,
            "kimi": self.providers.moonshot,
            "vllm": self.providers.vllm,
        }
        for keyword, provider in providers.items():
            if keyword in model and provider.api_key:
                return provider
        return None

    def get_api_key(self, model: str | None = None) -> str | None:
        """获取给定模型（或默认模型）的 API 密钥。回退到第一个可用的密钥。"""
        # 首先尝试按模型名称匹配
        matched = self._match_provider(model)
        if matched:
            return matched.api_key
        # 回退：返回第一个可用的密钥
        for provider in [
            self.providers.openrouter, self.providers.deepseek,
            self.providers.anthropic, self.providers.openai,
            self.providers.gemini, self.providers.zhipu,
            self.providers.dashscope, self.providers.moonshot,
            self.providers.vllm, self.providers.groq,
        ]:
            if provider.api_key:
                return provider.api_key
        return None
    
    def get_api_base(self, model: str | None = None) -> str | None:
        """根据模型名称获取 API 基础 URL。"""
        model = (model or self.agents.defaults.model).lower()
        if "openrouter" in model:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if any(k in model for k in ("zhipu", "glm", "zai")):
            return self.providers.zhipu.api_base
        if "vllm" in model:
            return self.providers.vllm.api_base
        return None
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
