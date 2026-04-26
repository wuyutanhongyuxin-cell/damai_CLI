from __future__ import annotations

from typing import cast

import httpx

from .exceptions import NeedSlideCaptcha, NotAuthenticated

_LOGIN_URL = "https://passport.damai.cn/newlogin/login.do"

# 大麦/淘宝 passport 需要的固定请求头
_BASE_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://passport.damai.cn/login",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# 滑块/风控信号关键词
_CAPTCHA_SIGNALS = ("RGV587_ERROR", "needCheckCode", "x5sec", "verifyType")


def _detect_captcha(body: dict) -> bool:
    """检测响应体里是否含滑块信号。"""
    content = str(body)
    return any(sig in content for sig in _CAPTCHA_SIGNALS)


def _extract_cookies(response: httpx.Response) -> dict[str, str]:
    """从 Set-Cookie 头解析所有 Cookie 键值对。"""
    return {name: val for name, val in response.cookies.items()}


def _check_success(body: dict) -> bool:
    """判断响应体是否表示登录成功。"""
    # 大麦 passport 成功时 code=200 或 returnValue 不含 error
    code = str(body.get("code", body.get("returnCode", "")))
    if code == "200":
        return True
    # 部分版本直接带 urls 或 token 字段
    return "urls" in body or "st" in body


def _post_login(payload: dict) -> httpx.Response:
    """发起 POST 请求，网络异常转 NotAuthenticated。"""
    try:
        with httpx.Client(headers=_BASE_HEADERS, follow_redirects=True, timeout=20) as client:
            resp = client.post(_LOGIN_URL, data=payload)
            resp.raise_for_status()
            return resp
    except httpx.HTTPError as exc:
        raise NotAuthenticated(f"网络请求失败: {exc}") from exc


def _parse_body(resp: httpx.Response) -> dict:
    """安全解析 JSON 响应体；解析失败返回空字典。"""
    try:
        return cast(dict, resp.json())
    except Exception:
        return {}


def password_login(username: str, password: str) -> dict[str, str]:
    """httpx POST 大麦 passport 登录接口，返回 Cookie dict。

    MVP：直接传明文密码（后续可接入 RSA 加密）。
    遇滑块信号 → NeedSlideCaptcha；登录失败 → NotAuthenticated。
    """
    payload = {
        "loginId": username,
        "password2": password,
        "keepLogin": "true",
        "appName": "damai",
        "appEntrance": "damai",
        "fromSite": "32",
    }
    resp = _post_login(payload)
    body = _parse_body(resp)

    if _detect_captcha(body) or _detect_captcha({"_raw": resp.text}):
        raise NeedSlideCaptcha("登录触发滑块验证，请改用二维码或浏览器登录")

    cookies = _extract_cookies(resp)
    if not _check_success(body) and not cookies:
        msg = body.get("message") or body.get("returnMessage") or "账号或密码错误"
        raise NotAuthenticated(f"密码登录失败: {msg}")

    return cookies
