"""nanobot 的实用工具函数。"""

from pathlib import Path
from datetime import datetime


def ensure_dir(path: Path) -> Path:
    """确保目录存在，必要时创建它。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_path() -> Path:
    """获取 nanobot 数据目录（~/.nanobot）。"""
    return ensure_dir(Path.home() / ".nanobot")


def get_workspace_path(workspace: str | None = None) -> Path:
    """
    获取工作区路径。
    
    参数:
        workspace: 可选的工作区路径。默认为 ~/.nanobot/workspace。
    
    返回:
        展开并确保存在的工作区路径。
    """
    if workspace:
        path = Path(workspace).expanduser()
    else:
        path = Path.home() / ".nanobot" / "workspace"
    return ensure_dir(path)


def get_sessions_path() -> Path:
    """获取会话存储目录。"""
    return ensure_dir(get_data_path() / "sessions")


def get_memory_path(workspace: Path | None = None) -> Path:
    """获取工作区内的记忆目录。"""
    ws = workspace or get_workspace_path()
    return ensure_dir(ws / "memory")


def get_skills_path(workspace: Path | None = None) -> Path:
    """获取工作区内的技能目录。"""
    ws = workspace or get_workspace_path()
    return ensure_dir(ws / "skills")


def today_date() -> str:
    """获取今天的日期，格式为 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


def timestamp() -> str:
    """获取 ISO 格式的当前时间戳。"""
    return datetime.now().isoformat()


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """将字符串截断到最大长度，如果被截断则添加后缀。"""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


def safe_filename(name: str) -> str:
    """将字符串转换为安全的文件名。"""
    # 替换不安全的字符
    unsafe = '<>:"/\\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    return name.strip()


def parse_session_key(key: str) -> tuple[str, str]:
    """
    将会话键解析为频道和聊天 ID。
    
    参数:
        key: 格式为 "channel:chat_id" 的会话键。
    
    返回:
        (频道, 聊天 ID) 元组。
    """
    parts = key.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return key, ""


def format_duration(seconds: float) -> str:
    """将秒数格式化为人类可读的持续时间。"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        return f"{seconds/60:.1f}分钟"
    else:
        return f"{seconds/3600:.1f}小时"


def sanitize_content(content: str, max_length: int = 4000) -> str:
    """
    清理内容以适应 LLM 上下文。
    
    参数:
        content: 原始内容。
        max_length: 最大长度。
    
    返回:
        清理后的内容。
    """
    # 截断
    if len(content) > max_length:
        content = content[:max_length] + "\n... (内容已截断)"
    
    return content
