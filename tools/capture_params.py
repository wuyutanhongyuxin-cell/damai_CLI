"""捕获核心 MTOP API 的完整 request.data + response body，用于 schema 对齐。

跑法：E:/python/python_3.13/python.exe tools/capture_params.py
输出：tmp_captures/<api_underscored>.json，每个唯一 (api, version) 记录一次完整
      url / method / data / body。同一 api 重复请求不覆盖（只记第一次）。

安全策略（严格只读）：
- 不点击"想看/收藏"（避免 favorite.add 写入）
- 不点击"立即预订/购买"（避免 trade.order.build 写入）
- 只做页面跳转 + 被动监听请求/响应
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COOKIES_PATH = Path.home() / ".damai-cli" / "cookies.json"
OUT_DIR = Path.cwd() / "tmp_captures"

# (label, url)；itemId 1039481556853 已验证仍 detail 有效（2026 i-dle 香港场）
PAGES: list[tuple[str, str]] = [
    ("home", "https://m.damai.cn/"),
    ("search", "https://m.damai.cn/shows/list.html?keyword=周杰伦"),
    ("category", "https://m.damai.cn/shows/category.html"),
    ("detail", "https://m.damai.cn/damai/detail/item.html?itemId=1039481556853"),
    ("mine", "https://m.damai.cn/shows/mine.html"),
]

MTOP_HOST_RE = re.compile(r"(mtop\.damai\.cn|h5api\.m\.taobao\.com|acs\.m\.taobao\.com)")
MTOP_RE = re.compile(r"/h5/(mtop\.[\w.]+)/(\d+\.\d+)/")
PAGE_DWELL = 8
GLOBAL_TIMEOUT = 360


def load_cookies() -> list[dict]:
    """cookies.json → playwright 格式，跨域塞 .damai.cn + .taobao.com 两份。"""
    raw = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    out: list[dict] = []
    for name, value in raw.items():
        for domain in (".damai.cn", ".taobao.com"):
            out.append({
                "name": name, "value": str(value), "domain": domain,
                "path": "/", "httpOnly": False, "secure": True, "sameSite": "None",
            })
    return out


def _extract_data(url: str) -> dict:
    """从 GET URL 的 data query param 中解析 JSON。"""
    qs = parse_qs(urlparse(url).query)
    raw = qs.get("data", [""])[0]
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw_data_str": raw}


class _Collector:
    """捕获每个唯一 (api, ver) 的第一次 request+response 并落盘。"""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.seen: set[tuple[str, str]] = set()
        self.pending: dict[str, tuple[str, str, dict, str]] = {}

    def on_request(self, req) -> None:
        url = req.url
        if not MTOP_HOST_RE.search(url):
            return
        m = MTOP_RE.search(url)
        if not m:
            return
        api, ver = m.group(1), m.group(2)
        if (api, ver) in self.seen:
            return
        self.pending[url] = (api, ver, _extract_data(url), req.method)

    async def on_response(self, resp) -> None:
        meta = self.pending.pop(resp.url, None)
        if meta is None:
            return
        api, ver, data, method = meta
        if (api, ver) in self.seen:
            return
        body = await self._read_body(resp)
        self.seen.add((api, ver))
        self._save(api, ver, method, resp.url, data, body)

    @staticmethod
    async def _read_body(resp) -> object:
        try:
            text = await resp.text()
        except Exception as exc:
            return {"_read_fail": str(exc)}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw_body_str": text[:5000]}

    def _save(self, api: str, ver: str, method: str, url: str, data: dict, body: object) -> None:
        record = {
            "api": api, "version": ver, "method": method,
            "request_url": url, "request_data": data, "response_body": body,
        }
        path = self.out_dir / f"{api.replace('.', '_')}.json"
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  [saved] {api}/{ver} -> {path.name}", flush=True)


async def _click_mine_readonly(page) -> None:
    """我的页：只点"订单"和"观演人"，绝不点"想看"（避免 favorite 写入）。"""
    for keyword in ("订单", "观演人"):
        try:
            loc = page.get_by_text(keyword, exact=False).first
            if await loc.count() == 0:
                print(f"  [{keyword}] 元素不存在", flush=True)
                continue
            print(f"  [点击] {keyword}", flush=True)
            await loc.click(timeout=5_000)
            await asyncio.sleep(PAGE_DWELL)
            await page.goto("https://m.damai.cn/shows/mine.html",
                            wait_until="domcontentloaded", timeout=20_000)
            await asyncio.sleep(3)
        except Exception as exc:
            print(f"  ! 点 {keyword} 失败: {exc}", flush=True)


async def _visit_pages(page, collector: _Collector) -> None:
    """按顺序遍历 PAGES；mine 页触发只读点击。"""
    for label, url in PAGES:
        print(f"\n[访问] {label} -> {url}", flush=True)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            print(f"  ! goto 失败: {exc}", flush=True)
            continue
        await asyncio.sleep(PAGE_DWELL)
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
        except Exception:
            pass
        if label == "mine":
            await _click_mine_readonly(page)


async def run() -> None:
    from camoufox.async_api import AsyncCamoufox

    OUT_DIR.mkdir(exist_ok=True)
    collector = _Collector(OUT_DIR)
    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(viewport={"width": 1280, "height": 860})
        await context.add_cookies(load_cookies())
        context.on("request", collector.on_request)
        context.on("response", lambda r: asyncio.create_task(collector.on_response(r)))
        page = await context.new_page()
        await _visit_pages(page, collector)
        await context.close()

    print(f"\n[DONE] 捕获 {len(collector.seen)} 个 API，落盘 {OUT_DIR}")
    for api, ver in sorted(collector.seen):
        print(f"  {api} / {ver}")


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(run(), timeout=GLOBAL_TIMEOUT))
    except asyncio.TimeoutError:
        print("[timeout] 整体超时退出", file=sys.stderr)
        sys.exit(1)
