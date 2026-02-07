"""频道管理器，用于协调聊天频道。"""

import asyncio
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import Config


class ChannelManager:
    """
    管理聊天频道并协调消息路由。
    
    职责：
    - 初始化启用的频道（Telegram、WhatsApp 等）
    - 启动/停止频道
    - 路由出站消息
    """
    
    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        
        self._init_channels()
    
    def _init_channels(self) -> None:
        """根据配置初始化频道。"""
        
        # Telegram 频道
        if self.config.channels.telegram.enabled:
            try:
                from nanobot.channels.telegram import TelegramChannel
                self.channels["telegram"] = TelegramChannel(
                    self.config.channels.telegram,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                )
                logger.info("Telegram 频道已启用")
            except ImportError as e:
                logger.warning(f"Telegram 频道不可用：{e}")
        
        # WhatsApp 频道
        if self.config.channels.whatsapp.enabled:
            try:
                from nanobot.channels.whatsapp import WhatsAppChannel
                self.channels["whatsapp"] = WhatsAppChannel(
                    self.config.channels.whatsapp, self.bus
                )
                logger.info("WhatsApp 频道已启用")
            except ImportError as e:
                logger.warning(f"WhatsApp 频道不可用：{e}")

        # Discord 频道
        if self.config.channels.discord.enabled:
            try:
                from nanobot.channels.discord import DiscordChannel
                self.channels["discord"] = DiscordChannel(
                    self.config.channels.discord, self.bus
                )
                logger.info("Discord 频道已启用")
            except ImportError as e:
                logger.warning(f"Discord 频道不可用：{e}")
        
        # 飞书频道
        if self.config.channels.feishu.enabled:
            try:
                from nanobot.channels.feishu import FeishuChannel
                self.channels["feishu"] = FeishuChannel(
                    self.config.channels.feishu, self.bus
                )
                logger.info("飞书频道已启用")
            except ImportError as e:
                logger.warning(f"飞书频道不可用：{e}")
    
    async def start_all(self) -> None:
        """启动 WhatsApp 频道和出站消息分发器。"""
        if not self.channels:
            logger.warning("没有启用的频道")
            return
        
        # 启动出站消息分发器
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())
        
        # 启动 WhatsApp 频道
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"正在启动 {name} 频道...")
            tasks.append(asyncio.create_task(channel.start()))
        
        # 等待所有频道完成（它们应该一直运行）
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self) -> None:
        """停止所有频道和分发器。"""
        logger.info("正在停止所有频道...")
        
        # 停止分发器
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        
        # 停止所有频道
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"已停止 {name} 频道")
            except Exception as e:
                logger.error(f"停止 {name} 时出错：{e}")
    
    async def _dispatch_outbound(self) -> None:
        """将出站消息分发到适当的频道。"""
        logger.info("出站消息分发器已启动")
        
        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"发送到 {msg.channel} 时出错：{e}")
                else:
                    logger.warning(f"未知频道：{msg.channel}")
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_channel(self, name: str) -> BaseChannel | None:
        """通过名称获取频道。"""
        return self.channels.get(name)
    
    def get_status(self) -> dict[str, Any]:
        """获取所有频道的状态。"""
        return {
            name: {
                "enabled": True,
                "running": channel._running
            }
            for name, channel in self.channels.items()
        }
    
    @property
    def enabled_channels(self) -> list[str]:
        """获取已启用频道名称列表。"""
        return list(self.channels.keys())
