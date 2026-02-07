"""用于后台任务执行的子代理管理器。"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool


class SubagentManager:
    """
    管理后台子代理执行。
    
    子代理是轻量级的代理实例，在后台运行以处理特定任务。
    它们共享相同的 LLM 提供商，但具有隔离的上下文和专注的系统提示词。
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """
        生成子代理在后台执行任务。
        
        参数:
            task: 子代理的任务描述。
            label: 任务的可选人类可读标签。
            origin_channel: 用于通知结果的频道。
            origin_chat_id: 用于通知结果的聊天 ID。
        
        返回:
            指示子代理已启动的状态消息。
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }
        
        # 创建后台任务
        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        
        # 完成时清理
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
        
        logger.info(f"生成子代理 [{task_id}]：{display_label}")
        return f"子代理 [{display_label}] 已启动（id：{task_id}）。完成后我会通知你。"
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """执行子代理任务并通知结果。"""
        logger.info(f"子代理 [{task_id}] 开始任务：{label}")
        
        try:
            # 构建子代理工具（无消息工具，无生成工具）
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())
            
            # 使用子代理特定提示词构建消息
            system_prompt = self._build_subagent_prompt(task)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # 运行代理循环（有限迭代次数）
            max_iterations = 15
            iteration = 0
            final_result: str | None = None
            
            while iteration < max_iterations:
                iteration += 1
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                )
                
                if response.has_tool_calls:
                    # 添加带有工具调用的助手消息
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })
                    
                    # 执行工具
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments)
                        logger.debug(f"子代理 [{task_id}] 执行：{tool_call.name}，参数：{args_str}")
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    break
            
            if final_result is None:
                final_result = "任务已完成，但未生成最终响应。"
            
            logger.info(f"子代理 [{task_id}] 成功完成")
            await self._announce_result(task_id, label, task, final_result, origin, "ok")
            
        except Exception as e:
            error_msg = f"错误：{str(e)}"
            logger.error(f"子代理 [{task_id}] 失败：{e}")
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """通过消息总线向主代理通知子代理结果。"""
        status_text = "成功完成" if status == "ok" else "失败"
        
        announce_content = f"""[子代理 '{label}' {status_text}]

任务：{task}

结果：
{result}

自然地为用户总结。保持简短（1-2 句话）。不要提及技术细节如"子代理"或任务 ID。"""
        
        # 作为系统消息注入以触发主代理
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug(f"子代理 [{task_id}] 已向 {origin['channel']}:{origin['chat_id']} 通知结果")
    
    def _build_subagent_prompt(self, task: str) -> str:
        """为子代理构建专注的系统提示词。"""
        return f"""# 子代理

你是由主代理生成来完成特定任务的子代理。

## 你的任务
{task}

## 规则
1. 保持专注 - 只完成分配的任务，不做其他事情
2. 你的最终响应将报告回主代理
3. 不要发起对话或承担旁支任务
4. 在你的发现中要简洁但信息丰富

## 你能做什么
- 在工作区中读写文件
- 执行 shell 命令
- 搜索网页并获取网页内容
- 彻底完成任务

## 你不能做什么
- 直接向用户发送消息（无消息工具可用）
- 生成其他子代理
- 访问主代理的对话历史

## 工作区
你的工作区位于：{self.workspace}

当你完成任务时，提供你的发现或行动的清晰总结。"""
    
    def get_running_count(self) -> int:
        """返回当前运行的子代理数量。"""
        return len(self._running_tasks)
