"""用于创建后台子代理的生成工具。"""

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """
    用于生成子代理以执行后台任务的工具。
    
    子代理异步运行，并在完成时将结果通知回主代理。
    """
    
    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """设置子代理通知的源上下文。"""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "spawn"
    
    @property
    def description(self) -> str:
        return (
            "生成一个子代理在后台处理任务。"
            "用于可以独立运行的复杂或耗时任务。"
            "子代理将完成任务并在完成后报告。"
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "子代理要完成的任务",
                },
                "label": {
                    "type": "string",
                    "description": "任务的可选简短标签（用于显示）",
                },
            },
            "required": ["task"],
        }
    
    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """
        生成子代理在后台执行给定任务。
        
        参数:
            task: 子代理的任务描述。
            label: 任务的可选人类可读标签。
            
        返回:
            指示子代理已启动的状态消息。
        """
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
        )
