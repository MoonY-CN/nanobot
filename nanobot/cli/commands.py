"""nanobot 的 CLI 命令。"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __version__, __logo__

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - 个人 AI 助手",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - 个人 AI 助手。"""
    pass


# ============================================================================
# 入门 / 设置
# ============================================================================


@app.command()
def onboard():
    """初始化 nanobot 配置和工作区。"""
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]配置已存在于 {config_path}[/yellow]")
        if not typer.confirm("覆盖？"):
            raise typer.Exit()
    
    # 创建默认配置
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] 已在 {config_path} 创建配置")
    
    # 创建工作区
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] 已在 {workspace} 创建工作区")
    
    # 创建默认引导文件
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} nanobot 已准备就绪！")
    console.print("\n下一步：")
    console.print("  1. 将你的 API 密钥添加到 [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     在 https://openrouter.ai/keys 获取")
    console.print("  2. 聊天：[cyan]nanobot agent -m \"你好！\"[/cyan]")
    console.print("\n[dim]想要 Telegram/WhatsApp？参见：https://github.com/HKUDS/nanobot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """创建默认工作区模板文件。"""
    templates = {
        "AGENTS.md": """# 代理指令

你是一个乐于助人的 AI 助手。要简洁、准确、友好。

## 指南

- 在采取行动之前始终解释你正在做什么
- 当请求不明确时请求澄清
- 使用工具来帮助完成任务
- 在记忆文件中记住重要信息
""",
        "SOUL.md": """# 灵魂

我是 nanobot，一个轻量级 AI 助手。

## 个性

- 乐于助人且友好
- 简洁明了
- 好奇且渴望学习

## 价值观

- 准确性优于速度
- 用户隐私和安全
- 行动透明
""",
        "USER.md": """# 用户

关于用户的信息放在这里。

## 偏好

- 沟通风格：（随意/正式）
- 时区：（你的时区）
- 语言：（你的首选语言）
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]已创建 {filename}[/dim]")
    
    # 创建 memory 目录和 MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# 长期记忆

此文件存储应在会话之间持久化的重要信息。

## 用户信息

（关于用户的重要事实）

## 偏好

（随时间了解的用户偏好）

## 重要笔记

（需要记住的事情）
""")
        console.print("  [dim]已创建 memory/MEMORY.md[/dim]")


# ============================================================================
# 网关 / 服务器
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="网关端口"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """启动 nanobot 网关。"""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} 正在端口 {port} 上启动 nanobot 网关...")
    
    config = load_config()
    
    # 创建组件
    bus = MessageBus()
    
    # 创建提供商（支持 OpenRouter、Anthropic、OpenAI、Bedrock）
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]错误：未配置 API 密钥。[/red]")
        console.print("在 ~/.nanobot/config.json 的 providers.openrouter.apiKey 下设置一个")
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    # 首先创建 cron 服务（回调在创建代理后设置）
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # 使用 cron 服务创建代理
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )
    
    # 设置 cron 回调（需要代理）
    async def on_cron_job(job: CronJob) -> str | None:
        """通过代理执行 cron 作业。"""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # 创建心跳服务
    async def on_heartbeat(prompt: str) -> str:
        """通过代理执行心跳。"""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 分钟
        enabled=True
    )
    
    # 创建频道管理器
    channels = ChannelManager(config, bus)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] 频道已启用：{', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]警告：未启用频道[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron：{cron_status['jobs']} 个计划任务")
    
    console.print(f"[green]✓[/green] 心跳：每 30 分钟")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\n正在关闭...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# 代理命令
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="发送给代理的消息"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="会话 ID"),
):
    """直接与代理交互。"""
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.agent.loop import AgentLoop
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]错误：未配置 API 密钥。[/red]")
        raise typer.Exit(1)

    bus = MessageBus()
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )
    
    if message:
        # 单条消息模式
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # 交互模式
        console.print(f"{__logo__} 交互模式（Ctrl+C 退出）\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]你：[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\n再见！")
                    break
        
        asyncio.run(run_interactive())




# ============================================================================
# 频道命令
# ============================================================================


channels_app = typer.Typer(help="管理频道")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """显示频道状态。"""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="频道状态")
    table.add_column("频道", style="cyan")
    table.add_column("已启用", style="green")
    table.add_column("配置", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]未配置[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """获取桥目录，如果需要则进行设置。"""
    import shutil
    import subprocess
    
    # 用户的桥位置
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # 检查是否已构建
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # 检查 npm
    if not shutil.which("npm"):
        console.print("[red]未找到 npm。请安装 Node.js >= 18。[/red]")
        raise typer.Exit(1)
    
    # 查找源桥：首先检查包数据，然后检查源目录
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge（已安装）
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge（开发）
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]未找到桥源。[/red]")
        console.print("尝试重新安装：pip install --force-reinstall nanobot")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} 正在设置桥...")
    
    # 复制到用户目录
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # 安装和构建
    try:
        console.print("  正在安装依赖...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  正在构建...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] 桥已准备就绪\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]构建失败：{e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """通过二维码链接设备。"""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} 正在启动桥...")
    console.print("扫描二维码以连接。\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]桥失败：{e}[/red]")
    except FileNotFoundError:
        console.print("[red]未找到 npm。请安装 Node.js。[/red]")


# ============================================================================
# Cron 命令
# ============================================================================

cron_app = typer.Typer(help="管理计划任务")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="包括已禁用的作业"),
):
    """列出计划任务。"""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("没有计划任务。")
        return
    
    table = Table(title="计划任务")
    table.add_column("ID", style="cyan")
    table.add_column("名称")
    table.add_column("计划")
    table.add_column("状态")
    table.add_column("下次运行")
    
    import time
    for job in jobs:
        # 格式化计划
        if job.schedule.kind == "every":
            sched = f"每 {(job.schedule.every_ms or 0) // 1000} 秒"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "一次性"
        
        # 格式化下次运行
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]已启用[/green]" if job.enabled else "[dim]已禁用[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="任务名称"),
    message: str = typer.Option(..., "--message", "-m", help="代理的消息"),
    every: int = typer.Option(None, "--every", "-e", help="每 N 秒运行一次"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron 表达式（例如 '0 9 * * *'）"),
    at: str = typer.Option(None, "--at", help="在指定时间运行一次（ISO 格式）"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="将响应传递给频道"),
    to: str = typer.Option(None, "--to", help="传递的接收者"),
    channel: str = typer.Option(None, "--channel", help="传递的频道（例如 'telegram'、'whatsapp'）"),
):
    """添加计划任务。"""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule
    
    # 确定计划类型
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]错误：必须指定 --every、--cron 或 --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] 已添加任务 '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="要移除的任务 ID"),
):
    """移除计划任务。"""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] 已移除任务 {job_id}")
    else:
        console.print(f"[red]未找到任务 {job_id}[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="任务 ID"),
    disable: bool = typer.Option(False, "--disable", help="禁用而不是启用"),
):
    """启用或禁用任务。"""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "已禁用" if disable else "已启用"
        console.print(f"[green]✓[/green] 任务 '{job.name}' {status}")
    else:
        console.print(f"[red]未找到任务 {job_id}[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="要运行的任务 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="即使已禁用也运行"),
):
    """手动运行任务。"""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] 任务已执行")
    else:
        console.print(f"[red]运行任务 {job_id} 失败[/red]")


# ============================================================================
# 状态命令
# ============================================================================


@app.command()
def status():
    """显示 nanobot 状态。"""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot 状态\n")
    console.print(f"配置：{config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"工作区：{workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        console.print(f"模型：{config.agents.defaults.model}")
        
        # 检查 API 密钥
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        
        console.print(f"OpenRouter API：{'[green]✓[/green]' if has_openrouter else '[dim]未设置[/dim]'}")
        console.print(f"Anthropic API：{'[green]✓[/green]' if has_anthropic else '[dim]未设置[/dim]'}")
        console.print(f"OpenAI API：{'[green]✓[/green]' if has_openai else '[dim]未设置[/dim]'}")
        console.print(f"Gemini API：{'[green]✓[/green]' if has_gemini else '[dim]未设置[/dim]'}")
        vllm_status = f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]未设置[/dim]"
        console.print(f"vLLM/本地：{vllm_status}")


if __name__ == "__main__":
    app()
