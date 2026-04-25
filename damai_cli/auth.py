from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone

from .cookies import CookieJar
from .exceptions import NotAuthenticated


class AuthManager:
    """四级登录调度器：saved → browser → qr（auto）；password 需显式指定。"""

    def __init__(self, cookies: CookieJar, client: object) -> None:
        # client 类型为 MtopClient，此处用 object 避免循环导入
        self._cookies = cookies
        self._client = client

    def current_status(self) -> dict:
        """按本地 Cookie 解析登录态：cookie2 / _nk_ 任一存在即算登录。

        damai 没有公开的 getuserinfo 接口（FAIL_SYS_API_NOT_FOUNDED），
        所以改用本地判定，user_id/nickname 从 unb/_nk_ 读出。
        """
        self._cookies.load()
        if not self._cookies.is_logged_in():
            return {"logged_in": False, "user_id": None, "nickname": None, "expires_at": None}
        # damai 自己的 Cookie 名：user_id / munb 是数字 ID，damai.cn_nickName 是 URL-encoded 昵称
        user_id = self._cookies.get("user_id") or self._cookies.get("munb") or self._cookies.get("unb") or None
        raw_nick = (
            self._cookies.get("damai.cn_nickName")
            or self._cookies.get("_nk_")
            or self._cookies.get("tracknick")
        )
        nickname = urllib.parse.unquote(raw_nick) if raw_nick else None
        return {
            "logged_in": True,
            "user_id": user_id,
            "nickname": nickname,
            "expires_at": self._expires_at_iso(),
        }

    def _expires_at_iso(self) -> str | None:
        """根据 Cookie 文件 mtime + TTL 计算过期时间 ISO 8601。"""
        if not self._cookies.path.exists():
            return None
        mtime = self._cookies.path.stat().st_mtime
        exp_ts = mtime + CookieJar.TTL_SECONDS
        return datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()

    def _try_saved(self) -> dict[str, str]:
        """尝试直接加载已保存 Cookie；过期或未登录则抛 NotAuthenticated。"""
        if self._cookies.is_expired():
            raise NotAuthenticated("已保存的 Cookie 已过期")
        cookies = self._cookies.load()
        if not cookies:
            raise NotAuthenticated("无已保存 Cookie")
        # 简单校验登录标志
        if not self._cookies.is_logged_in():
            raise NotAuthenticated("已保存 Cookie 不含登录标志")
        return cookies

    def _try_browser(self) -> dict[str, str]:
        """从浏览器抓 Cookie；失败抛 NotAuthenticated。"""
        from .browser_cookie import extract_cookies
        return extract_cookies()

    def _try_qr(self, timeout: int = 180, headed: bool = False) -> dict[str, str]:
        """发起 QR 扫码登录。"""
        from .qr_login import qr_login
        return qr_login(timeout=timeout, headed=headed)

    def _prompt_credentials(self) -> tuple[str, str]:
        """从环境变量或交互提示读取用户名和密码。"""
        username = os.environ.get("DAMAI_USERNAME") or input("大麦账号: ").strip()
        password = os.environ.get("DAMAI_PASSWORD") or input("密码: ").strip()
        if not username or not password:
            raise NotAuthenticated("未提供账号或密码")
        return username, password

    def _finalize(self, cookies: dict[str, str]) -> dict:
        """保存 Cookie 并回填用户信息，返回 current_status。"""
        self._cookies.save(cookies)
        return self.current_status()

    def login(self, method: str = "auto", *, headed: bool = False) -> dict:
        """按指定方法登录，返回 current_status 字典。

        auto: saved → browser → qr（password 不走 auto）
        """
        if method == "saved":
            return self._finalize(self._try_saved())
        if method == "browser":
            return self._finalize(self._try_browser())
        if method == "qr":
            return self._finalize(self._try_qr(headed=headed))
        if method == "password":
            username, password = self._prompt_credentials()
            from .password_login import password_login
            return self._finalize(password_login(username, password))
        if method == "auto":
            return self._auto_login()
        raise NotAuthenticated(f"不支持的登录方式: {method}")

    def _auto_login(self) -> dict:
        """auto 顺序：saved → browser → qr；逐级尝试，全失败再抛异常。"""
        for attempt in (self._try_saved, self._try_browser, self._try_qr):
            try:
                cookies = attempt()
                return self._finalize(cookies)
            except NotAuthenticated:
                continue
        raise NotAuthenticated("所有登录方式均失败，请检查网络或手动扫码")

    def logout(self) -> None:
        """清除本地 Cookie 文件，完成登出。"""
        self._cookies.clear()
