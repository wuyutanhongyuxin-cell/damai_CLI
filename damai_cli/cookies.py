from __future__ import annotations

import json
import time
from pathlib import Path

from .config import COOKIES_FILE


class CookieJar:
    """JSON 持久化 Cookie 管理器，TTL=7 天。"""

    TTL_SECONDS = 7 * 86400

    def __init__(self, path: Path | None = None) -> None:
        # 未指定路径时使用全局默认路径
        self._path: Path = path if path is not None else COOKIES_FILE
        self._data: dict[str, str] = {}

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, str]:
        """从 JSON 文件读取 Cookie；文件不存在返回空字典。"""
        if not self._path.exists():
            self._data = {}
            return {}
        with self._path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        # 防御：只保留字符串值
        self._data = {k: str(v) for k, v in raw.items() if isinstance(k, str)}
        return dict(self._data)

    def save(self, cookies: dict[str, str]) -> None:
        """将 cookies 写入 JSON 文件（UTF-8），同时更新内存缓存。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = dict(cookies)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def update(self, cookies: dict[str, str]) -> None:
        """合并新 Cookie 并持久化；不暴露 __setitem__。"""
        # 先确保内存数据是最新的
        if not self._data and self._path.exists():
            self.load()
        self._data.update(cookies)
        self.save(self._data)

    def clear(self) -> None:
        """清空内存缓存并删除文件。"""
        self._data = {}
        if self._path.exists():
            self._path.unlink()

    def get(self, key: str) -> str | None:
        """读取单个 Cookie 值；未找到返回 None。"""
        if not self._data:
            self.load()
        return self._data.get(key)

    def get_token(self) -> str | None:
        """从 _m_h5_tk 中提取前半段 MD5（32 位），用于 MTOP 签名。"""
        raw = self.get("_m_h5_tk")
        if not raw:
            return None
        # 格式：<32位MD5>_<时间戳>
        return raw.split("_")[0]

    def as_header(self) -> str:
        """拼接 Cookie 请求头字符串，格式：k1=v1; k2=v2。"""
        if not self._data:
            self.load()
        return "; ".join(f"{k}={v}" for k, v in self._data.items())

    def is_expired(self) -> bool:
        """根据文件 mtime + TTL 判断是否过期；文件不存在视为已过期。"""
        if not self._path.exists():
            return True
        mtime = self._path.stat().st_mtime
        return (time.time() - mtime) > self.TTL_SECONDS

    def is_logged_in(self) -> bool:
        """判断是否处于登录态：login=true 或存在 _nk_/cookie2。"""
        if not self._data:
            self.load()
        if self._data.get("login") == "true":
            return True
        return "_nk_" in self._data or "cookie2" in self._data
