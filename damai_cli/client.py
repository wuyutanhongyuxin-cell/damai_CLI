from __future__ import annotations

import random
import time

import httpx

from . import config as cfg
from .exceptions import (
    IpBlocked,
    ItemNotStarted,
    ItemSoldOut,
    NeedSlideCaptcha,
    NetworkError,
    NotAuthenticated,
    RateLimited,
    RealNameRequired,
    SessionExpired,
    TokenEmpty,
    UpstreamError,
)

# 重试间隔（秒）：指数退避，最多 4 次
_RATE_BACKOFF = (5, 10, 20, 30)

# damai H5 所有 MTOP 请求必带的业务参数；缺任意一个接口会拒
_COMMON_MTOP_PARAMS = {
    "platform": "8",
    "comboChannel": "2",
    "dmChannel": "damai@damaih5_h5",
}


# 内部哨兵异常，不对外暴露
class _TokenNeedRefresh(Exception):
    pass


def _jitter_sleep(base: float = 1.0) -> None:
    # Gaussian jitter 延迟：5% 概率额外 2-5 秒，仿 xhs-cli 防风控
    delay = max(0.0, base + random.gauss(0, 0.3))
    if random.random() < 0.05:
        delay += random.uniform(2.0, 5.0)
    time.sleep(delay)


def _map_ret_error(ret_str: str, raw_body: dict) -> Exception:
    """将 mtop ret 字符串映射到对应异常实例。"""
    r = ret_str.upper()
    # Token 类错误由调用方处理，不在此映射
    if "SESSION_EXPIRED" in r or "FAIL_SYS_SESSION_EXPIRED" in r:
        return SessionExpired(ret_str)
    if "RGV587" in r or "SLIDE" in r or "X5SEC" in r:
        return NeedSlideCaptcha(ret_str)
    if "SM_CODE::1999" in r or "IP_BLOCK" in r:
        return IpBlocked(ret_str)
    if "SOLD_OUT" in r or "SOLDOUT" in r:
        return ItemSoldOut(ret_str)
    if "NOT_STARTED" in r or "NOT_START" in r or "PRESALE" in r:
        return ItemNotStarted(ret_str)
    if "REAL_NAME" in r or "REALNAME" in r:
        return RealNameRequired(ret_str)
    if "FLOW_LIMIT" in r or "RATE_LIMIT" in r:
        return RateLimited(ret_str)
    if "FAIL_SYS" in r:
        return UpstreamError(ret_str)
    return UpstreamError(ret_str)


def _extract_set_cookies(response: httpx.Response) -> dict[str, str]:
    """从响应头解析 Set-Cookie 字段，返回 {name: value}。"""
    cookies: dict[str, str] = {}
    for header_val in response.headers.get_list("set-cookie"):
        # 只取第一个 name=value 片段
        part = header_val.split(";")[0].strip()
        if "=" in part:
            name, _, val = part.partition("=")
            cookies[name.strip()] = val.strip()
    return cookies


class MtopClient:
    def __init__(
        self,
        cookies=None,  # CookieJar | None
        *,
        timeout: float = 15.0,
        user_agent: str | None = None,
        host: str = "mtop.damai.cn",
    ) -> None:
        # 延迟导入避免循环依赖
        from .cookies import CookieJar

        self._jar = cookies if cookies is not None else CookieJar()
        self._host = host
        ua = user_agent or cfg.DEFAULT_CONFIG["user_agent"]
        self._http = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": ua, "Referer": "https://www.damai.cn/"},
            follow_redirects=True,
        )

    def _send_http(self, url: str, params: dict, headers: dict, method: str) -> httpx.Response:
        """发送 HTTP GET 或 POST，网络错误转为 NetworkError。"""
        try:
            if method.upper() == "POST":
                return self._http.post(url, data=params, headers=headers)
            return self._http.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise NetworkError(str(exc)) from exc

    def _do_request(self, api: str, version: str, data: dict, method: str) -> dict:
        """执行一次 HTTP 请求（不含重试逻辑）；返回解析后的 JSON body。"""
        from . import signing

        token = self._jar.get_token() or ""
        merged = {**_COMMON_MTOP_PARAMS, **data}  # 调用方字段覆盖公共参数
        params = signing.build_mtop_params(api, version, merged, token)
        url = signing.build_mtop_url(api, version, self._host)
        cookie_header = self._jar.as_header()
        headers = {"Cookie": cookie_header} if cookie_header else {}

        resp = self._send_http(url, params, headers, method)
        # 合并 Set-Cookie 回 jar
        new_cookies = _extract_set_cookies(resp)
        if new_cookies:
            self._jar.update(new_cookies)
            self._jar.save(dict(self._jar.load()))
        if resp.status_code == 429:
            raise RateLimited(f"HTTP 429: {resp.text[:120]}")
        try:
            return resp.json()
        except Exception as exc:
            raise UpstreamError(f"响应非 JSON: {resp.text[:200]}") from exc

    def _parse_body(self, body: dict) -> dict:
        """从 body 中提取 data；ret 非 SUCCESS 时抛异常。"""
        ret_list: list = body.get("ret") or []
        for ret_str in ret_list:
            upper = str(ret_str).upper()
            if "SUCCESS" in upper:
                continue
            # Token 空/过期：由 request() 上层处理，透传特殊标记
            if "TOKEN_EMPTY" in upper or "TOKEN_EXPIRED" in upper:
                raise _TokenNeedRefresh(ret_str)
            raise _map_ret_error(ret_str, body)
        return body.get("data") or {}

    def _single_call(self, api: str, version: str, data: dict, method: str) -> dict:
        """带 token 空处理的单次调用；token 失效时重签重试 1 次。"""
        body = self._do_request(api, version, data, method)
        try:
            return self._parse_body(body)
        except _TokenNeedRefresh:
            # 尝试用 Set-Cookie 里最新 token 重签
            new_token = self._jar.get_token()
            if not new_token:
                raise TokenEmpty("token 为空，请重新登录")
            body2 = self._do_request(api, version, data, method)
            try:
                return self._parse_body(body2)
            except _TokenNeedRefresh:
                raise TokenEmpty("重签后 token 仍失效，请重新登录")

    def _retry_call(self, api: str, version: str, data: dict, method: str) -> dict:
        """RateLimited 指数退避重试，最多 4 次。"""
        for i, wait in enumerate(_RATE_BACKOFF):
            try:
                return self._single_call(api, version, data, method)
            except RateLimited:
                if i == len(_RATE_BACKOFF) - 1:
                    raise
                time.sleep(wait)
        return self._single_call(api, version, data, method)

    def request(
        self,
        api: str,
        version: str = "1.0",
        data: dict | None = None,
        *,
        need_login: bool = False,
        method: str = "GET",
    ) -> dict:
        """发送 MTOP 请求；返回 upstream 响应里的 data 字段。"""
        if need_login and not self._jar.is_logged_in():
            raise NotAuthenticated("请先执行 damai login")
        _jitter_sleep(cfg.DEFAULT_CONFIG.get("request_delay", 1.0))
        return self._retry_call(api, version, data or {}, method)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MtopClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

