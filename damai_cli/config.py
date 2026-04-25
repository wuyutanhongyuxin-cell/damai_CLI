from __future__ import annotations

import os
from pathlib import Path

import yaml

# 配置目录固定在用户主目录下
CONFIG_DIR: Path = Path.home() / ".damai-cli"
CONFIG_FILE: Path = CONFIG_DIR / "config.yaml"
COOKIES_FILE: Path = CONFIG_DIR / "cookies.json"
CACHE_DIR: Path = CONFIG_DIR / "cache"
QR_FILE: Path = CONFIG_DIR / "qr.png"

# Chrome 最新桌面 UA（写死，避免每次动态生成引入不确定性）
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 默认配置项；output=auto 表示运行时由 output.detect_mode() 自动决定
DEFAULT_CONFIG: dict = {
    "output": "auto",
    "timeout": 15,
    "user_agent": _CHROME_UA,
    # gaussian jitter 基准：实际延迟 = request_delay + N(0, 0.3)，防风控
    "request_delay": 1.0,
}


def ensure_dirs() -> None:
    """创建 CONFIG_DIR 和 CACHE_DIR，幂等。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """读取 config.yaml；文件不存在则返回默认配置副本。"""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    with CONFIG_FILE.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    # 用默认值填充缺失键，保证调用方拿到完整字典
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(cfg: dict) -> None:
    """将配置写入 config.yaml（UTF-8，human-readable YAML）。"""
    ensure_dirs()
    with CONFIG_FILE.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, default_flow_style=False)


def get_env(key: str, default: str | None = None) -> str | None:
    """读取 DAMAI_<KEY> 环境变量；未设置时返回 default。"""
    env_key = f"DAMAI_{key.upper()}"
    return os.environ.get(env_key, default)
