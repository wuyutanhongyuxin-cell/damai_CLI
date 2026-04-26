from __future__ import annotations

import http.cookiejar
from collections.abc import Callable

import browser_cookie3

from .exceptions import NotAuthenticated

# 默认抓取的浏览器列表
_DEFAULT_BROWSERS: list[str] = ["chrome", "edge", "firefox", "brave"]

# browser_cookie3 支持的浏览器函数映射
_BROWSER_LOADERS: dict[str, Callable[..., http.cookiejar.CookieJar]] = {
    "chrome": browser_cookie3.chrome,
    "edge": browser_cookie3.edge,
    "firefox": browser_cookie3.firefox,
    "brave": browser_cookie3.brave,
}

# 需要抓取的域名
_TARGET_DOMAINS = ["damai.cn", "taobao.com"]


def _load_browser(name: str, domain: str) -> http.cookiejar.CookieJar | None:
    """从指定浏览器加载某域 Cookie；浏览器未安装/异常返回 None。"""
    loader = _BROWSER_LOADERS.get(name)
    if loader is None:
        return None
    try:
        return loader(domain_name=domain)
    except Exception:
        # 浏览器未安装或 profile 锁定时静默跳过
        return None


def _jar_to_dict(jar: http.cookiejar.CookieJar | None) -> dict[str, str]:
    """CookieJar 转换为扁平 dict；值以后出现的覆盖先出现的。"""
    if jar is None:
        return {}
    return {c.name: c.value for c in jar if c.value is not None}


def extract_cookies(browsers: list[str] | None = None) -> dict[str, str]:
    """用 browser-cookie3 抓 .damai.cn 和 .taobao.com 的 Cookie 并合并。

    browsers 默认 ['chrome','edge','firefox','brave']。
    合并优先级：damai.cn 覆盖 taobao.com；后列出的浏览器覆盖前面的。
    无 Cookie → NotAuthenticated。
    """
    browser_list = browsers if browsers is not None else _DEFAULT_BROWSERS
    merged: dict[str, str] = {}

    for browser_name in browser_list:
        for domain in _TARGET_DOMAINS:
            jar = _load_browser(browser_name, domain)
            cookies = _jar_to_dict(jar)
            # damai.cn 域后加载，会覆盖 taobao.com 同名键——符合优先级
            merged.update(cookies)

    if not merged:
        raise NotAuthenticated("未从浏览器找到 damai.cn / taobao.com 的 Cookie，请先在浏览器登录大麦")

    return merged
