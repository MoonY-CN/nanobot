"""定时任务类型定义。"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CronSchedule:
    """定时任务的调度定义。"""
    kind: Literal["at", "every", "cron"]
    # 用于 "at"：毫秒时间戳
    at_ms: int | None = None
    # 用于 "every"：毫秒间隔
    every_ms: int | None = None
    # 用于 "cron"：cron 表达式（例如 "0 9 * * *"）
    expr: str | None = None
    # cron 表达式的时区
    tz: str | None = None


@dataclass
class CronPayload:
    """任务运行时要执行的操作。"""
    kind: Literal["system_event", "agent_turn"] = "agent_turn"
    message: str = ""
    # 是否将响应发送到频道
    deliver: bool = False
    channel: str | None = None  # 例如 "whatsapp"
    to: str | None = None  # 例如电话号码


@dataclass
class CronJobState:
    """任务的运行时状态。"""
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None


@dataclass
class CronJob:
    """一个定时任务。"""
    id: str
    name: str
    enabled: bool = True
    schedule: CronSchedule = field(default_factory=lambda: CronSchedule(kind="every"))
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False


@dataclass
class CronStore:
    """定时任务的持久化存储。"""
    version: int = 1
    jobs: list[CronJob] = field(default_factory=list)
