from __future__ import annotations

import asyncio
import base64
import time

import httpx
import qrcode_terminal

from . import config
from .exceptions import NotAuthenticated

_LOGIN_URL = "https://passport.damai.cn/login"
# QR 选择器宽泛兜底：大麦历史上用 canvas 渲染；也覆盖 img/iframe 兜底
_QR_SELECTOR = (
    "canvas, img[src*='qrcode'], img[src*='login'], "
    "img[alt*='二维码'], img[alt*='qrcode'], #login-qrcode canvas, iframe"
)
# 点击切到扫码 tab 的候选（页面可能默认在账密 tab）
_QR_TAB_SELECTORS = [
    "text=扫码登录",
    ".iconfont-qrcode",
    ".qrcode-login",
    "[data-spm*='qr']",
]
_POLL_INTERVAL = 2  # 秒
# 登录成功后预期的落脚域；不跳到这几个域上一概不认（规避扫完码但二次验证未完成时 cookie 先到的误判）
_SUCCESS_DOMAINS = ("damai.cn", "taobao.com", "tmall.com")
# URL 跳离 passport 后，再给 cookie/重定向一个稳定期
_SETTLE_AFTER_LOGIN = 3


def _download_qr_image(src: str) -> None:
    """将 QR 图片 URL 下载到 config.QR_FILE。"""
    config.ensure_dirs()
    resp = httpx.get(src, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    config.QR_FILE.write_bytes(resp.content)


def _handle_qr_src(src: str) -> None:
    """保存 QR 图到本地，提示用户扫描；不要把 URL 再次编码成 QR（阿里认不得）。"""
    if src.startswith("http"):
        _download_qr_image(src)
        print(f"[QR] 已下载至 {config.QR_FILE}")
        print(f"[QR] 用大麦/淘宝 App 扫描该图片 (或直接浏览器打开: {src})")
    elif src.startswith("data:image"):
        _, b64data = src.split(",", 1)
        config.ensure_dirs()
        config.QR_FILE.write_bytes(base64.b64decode(b64data))
        print(f"[QR] 已保存至 {config.QR_FILE}，用手机扫描图片登录")
    else:
        # src 是纯文本 login_token URL，可在终端直接渲染成 QR
        qrcode_terminal.draw(src)


async def _poll_login(page: object, context: object, timeout: int) -> None:
    """轮询直到登录成功：URL 跳离 passport 域并抵达 damai/taobao 主站才算完成。

    不用 cookie 名判定 —— 扫码成功但二次验证未完成时，unb/tracknick/cookie2
    这些 cookie 会先被写上，但登录其实还没走完。只有 URL 跳到主站才算真完成。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(_POLL_INTERVAL)  # type: ignore[attr-defined]
        try:
            url = page.url  # type: ignore[attr-defined]
        except Exception:
            continue
        if not url or url.startswith("about:") or "passport." in url:
            continue
        if any(d in url for d in _SUCCESS_DOMAINS):
            await asyncio.sleep(_SETTLE_AFTER_LOGIN)  # type: ignore[attr-defined]
            return
    raise NotAuthenticated("登录超时，请重试")


async def _try_click_qr_tab(page: object) -> None:
    """页面若默认在账密 tab，尝试切到扫码；找不到就跳过。"""
    for sel in _QR_TAB_SELECTORS:
        try:
            el = await page.query_selector(sel)  # type: ignore[attr-defined]
            if el:
                await el.click()
                await asyncio.sleep(1)
                return
        except Exception:
            continue


async def _dump_debug(page: object) -> None:
    """失败时截图 + 存 HTML 便于排查，异常静默。"""
    try:
        config.ensure_dirs()
        await page.screenshot(path=str(config.CONFIG_DIR / "qr_debug.png"), full_page=True)  # type: ignore[attr-defined]
        html = await page.content()  # type: ignore[attr-defined]
        (config.CONFIG_DIR / "qr_debug.html").write_text(html, encoding="utf-8")
    except Exception:
        pass


async def _headless_qr_flow(page: object, context: object, timeout: int) -> dict[str, str]:
    """headless 模式：探测 QR 元素、下载图、打印提示，然后轮询登录。"""
    await asyncio.sleep(3)
    await _try_click_qr_tab(page)
    try:
        qr_elem = await page.wait_for_selector(_QR_SELECTOR, timeout=20_000)  # type: ignore[attr-defined]
        src = await qr_elem.get_attribute("src") or ""
        _handle_qr_src(src)
    except Exception:
        await _dump_debug(page)
        raise
    await _poll_login(page, context, timeout)
    raw = await context.cookies()  # type: ignore[attr-defined]
    return {c["name"]: c["value"] for c in raw}


async def _headed_flow(page: object, context: object, timeout: int) -> dict[str, str]:
    """headed 模式：直接让用户在浏览器里完成登录（扫码/密码/短信均可）。"""
    # 等资源加载完，避免用户看到半截页面；networkidle 拿不到就退回 load
    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)  # type: ignore[attr-defined]
    except Exception:
        try:
            await page.wait_for_load_state("load", timeout=10_000)  # type: ignore[attr-defined]
        except Exception:
            pass
    print(f"[登录] 请在弹出的浏览器窗口中完成登录（扫码/密码/短信均可）")
    print(f"[登录] CLI 将轮询登录状态，最长等待 {timeout} 秒")
    await _poll_login(page, context, timeout)
    raw = await context.cookies()  # type: ignore[attr-defined]
    cookies = {c["name"]: c["value"] for c in raw}
    # 透明度：告诉用户到底抓到了哪些关键 Cookie，方便判断是轮询问题还是接口问题
    important = {"_m_h5_tk", "cookie2", "_nk_", "unb", "tracknick", "login"}
    hits = sorted(important & cookies.keys())
    try:
        final_url = page.url  # type: ignore[attr-defined]
    except Exception:
        final_url = "?"
    print(f"[登录] 抓到 {len(cookies)} 条 Cookie，关键标记命中: {hits or '无'}；最终 URL: {final_url}")
    return cookies


async def _run_qr_login(timeout: int, headed: bool = False) -> dict[str, str]:
    from camoufox.async_api import AsyncCamoufox  # 可选依赖，延迟导入

    # 给 headed 窗口一个够大的渲染区域，否则 damai 登录页会裁剪/错位
    viewport = {"width": 1280, "height": 860}
    async with AsyncCamoufox(headless=not headed) as browser:
        context = await browser.new_context(viewport=viewport)
        page = await context.new_page()
        try:
            wait = "load" if headed else "domcontentloaded"
            await page.goto(_LOGIN_URL, wait_until=wait, timeout=60_000)
            if headed:
                return await _headed_flow(page, context, timeout)
            return await _headless_qr_flow(page, context, timeout)
        finally:
            await context.close()


def qr_login(timeout: int = 180, headed: bool = False) -> dict[str, str]:
    """camoufox 打开登录页、展示 QR 码、轮询登录态，成功返回 Cookie dict。

    headed=True 时弹出浏览器窗口，适合在桌面环境直接扫屏幕上的 QR。
    失败/超时 → NotAuthenticated。
    """
    try:
        return asyncio.run(_run_qr_login(timeout, headed=headed))
    except NotAuthenticated:
        raise
    except Exception as exc:
        raise NotAuthenticated(f"QR 登录失败: {exc}") from exc
