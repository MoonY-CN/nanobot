"""使用 Node.js 桥的 WhatsApp 频道实现。"""

import asyncio
import json
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import WhatsAppConfig


class WhatsAppChannel(BaseChannel):
    """
    连接到 Node.js 桥的 WhatsApp 频道。
    
    该桥使用 @whiskeysockets/baileys 处理 WhatsApp Web 协议。
    Python 和 Node.js 之间通过 WebSocket 通信。
    """
    
    name = "whatsapp"
    
    def __init__(self, config: WhatsAppConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self._ws = None
        self._connected = False
    
    async def start(self) -> None:
        """通过连接到桥启动 WhatsApp 频道。"""
        import websockets
        
        bridge_url = self.config.bridge_url
        
        logger.info(f"正在连接到 {bridge_url} 的 WhatsApp 桥...")
        
        self._running = True
        
        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("已连接到 WhatsApp 桥")
                    
                    # 监听消息
                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error(f"处理桥消息时出错：{e}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"WhatsApp 桥连接错误：{e}")
                
                if self._running:
                    logger.info("5 秒后重新连接...")
                    await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """停止 WhatsApp 频道。"""
        self._running = False
        self._connected = False
        
        if self._ws:
            await self._ws.close()
            self._ws = None
    
    async def send(self, msg: OutboundMessage) -> None:
        """通过 WhatsApp 发送消息。"""
        if not self._ws or not self._connected:
            logger.warning("WhatsApp 桥未连接")
            return
        
        try:
            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content
            }
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"发送 WhatsApp 消息时出错：{e}")
    
    async def _handle_bridge_message(self, raw: str) -> None:
        """处理来自桥的消息。"""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"来自桥的无效 JSON：{raw[:100]}")
            return
        
        msg_type = data.get("type")
        
        if msg_type == "message":
            # 来自 WhatsApp 的传入消息
            sender = data.get("sender", "")
            content = data.get("content", "")
            
            # sender 通常是：<phone>@s.whatsapp.net
            # 仅提取电话号码作为 chat_id
            chat_id = sender.split("@")[0] if "@" in sender else sender
            
            # 处理语音转录（如果是语音消息）
            if content == "[语音消息]":
                logger.info(f"收到来自 {chat_id} 的语音消息，但桥的直接下载尚不支持。")
                content = "[语音消息：WhatsApp 转录尚不可用]"
            
            await self._handle_message(
                sender_id=chat_id,
                chat_id=sender,  # 使用完整 JID 进行回复
                content=content,
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": data.get("isGroup", False)
                }
            )
        
        elif msg_type == "status":
            # 连接状态更新
            status = data.get("status")
            logger.info(f"WhatsApp 状态：{status}")
            
            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False
        
        elif msg_type == "qr":
            # 认证用的二维码
            logger.info("在桥终端扫描二维码以连接 WhatsApp")
        
        elif msg_type == "error":
            logger.error(f"WhatsApp 桥错误：{data.get('error')}")
