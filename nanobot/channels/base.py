"""聊天平台的频道基类接口。"""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


class BaseChannel(ABC):
    """
    聊天频道实现的抽象基类。
    
    每个频道（Telegram、Discord 等）都应该实现此接口以集成到 nanobot 消息总线。
    """
    
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageBus):
        """
        初始化频道。
        
        参数:
            config: 频道特定的配置。
            bus: 用于通信的消息总线。
        """
        self.config = config
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """
        启动频道并开始监听消息。
        
        这应该是一个长期运行的异步任务，需要：
        1. 连接到聊天平台
        2. 监听入站消息
        3. 通过 _handle_message() 将消息转发到总线
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止频道并清理资源。"""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        通过此频道发送消息。
        
        参数:
            msg: 要发送的消息。
        """
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """
        检查发送者是否被允许使用此机器人。
        
        参数:
            sender_id: 发送者的标识符。
        
        返回:
            如果允许返回 True，否则返回 False。
        """
        allow_list = getattr(self.config, "allow_from", [])
        
        # 如果没有允许列表，允许所有人
        if not allow_list:
            return True
        
        sender_str = str(sender_id)
        if sender_str in allow_list:
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in allow_list:
                    return True
        return False
    
    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        处理来自聊天平台的入站消息。
        
        此方法检查权限并将消息转发到总线。
        
        参数:
            sender_id: 发送者的标识符。
            chat_id: 聊天/频道标识符。
            content: 消息内容。
            media: 可选的媒体 URL 列表。
            metadata: 可选的频道特定元数据。
        """
        # 检查发送者是否在允许列表中
        if not self.is_allowed(sender_id):
            logger.warning(f"拒绝来自 {sender_id} 的消息（不在允许列表中）")
            return
        
        # 创建入站消息事件
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {}
        )
        
        # 发布到总线
        await self.bus.publish_inbound(msg)
