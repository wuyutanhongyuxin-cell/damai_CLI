from __future__ import annotations

import click

from ._common import run_command, get_client
from ..output import ok
from ..cookies import CookieJar


def _make_auth_manager():
    """构建 AuthManager；client 用于 current_status 验证。"""
    from ..auth import AuthManager
    jar = CookieJar()
    client = get_client()
    return AuthManager(cookies=jar, client=client)


def register(cli: click.Group) -> None:

    @cli.command(name="login")
    @click.option(
        "--method",
        type=click.Choice(["auto", "browser", "qr", "password", "saved"]),
        default="auto",
        show_default=True,
        help="登录方式",
    )
    @click.option("--headed", is_flag=True, help="QR 登录时弹出真浏览器窗口（桌面环境推荐）")
    @run_command
    def login(method: str, headed: bool):
        # auto: saved → browser → qr；password 需显式指定
        mgr = _make_auth_manager()
        status = mgr.login(method=method, headed=headed)
        return ok(status)

    @cli.command(name="logout")
    @run_command
    def logout():
        # 清除本地 Cookie 并提示
        mgr = _make_auth_manager()
        mgr.logout()
        return ok({"message": "已登出，本地 Cookie 已清除"})

    @cli.command(name="status")
    @run_command
    def status():
        # 调接口验证当前登录态，返回完整状态
        mgr = _make_auth_manager()
        return ok(mgr.current_status())

    @cli.command(name="whoami")
    @run_command
    def whoami():
        # 仅返回 nickname 和 user_id
        mgr = _make_auth_manager()
        full = mgr.current_status()
        return ok({
            "nickname": full.get("nickname"),
            "user_id": full.get("user_id"),
        })
