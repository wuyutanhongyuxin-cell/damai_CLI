"""抓 damai 剩余 MTOP api：build/submit/pay-url/favorites。

跑法：E:/python/python_3.13/python.exe tools/capture_mtop_v2.py
专攻 v1 没抓到的 4 类：
  - build/submit/pay: 点详情页"立即预订"跳建单/支付（本脚本只到建单页，不真实 submit）
  - favorites: 收藏列表 / 添加收藏
副作用：阶段 2 可能触发真实建单；阶段 3 策略 A 可能真实写收藏。
"""
from __future__ import annotations

import asyncio, json, re, sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COOKIES_PATH = Path.home() / ".damai-cli" / "cookies.json"
MTOP_HOST_RE = re.compile(r"(mtop\.damai\.cn|h5api\.m\.taobao\.com|acs\.m\.taobao\.com)")
MTOP_RE = re.compile(r"/h5/(mtop\.[\w.]+)/(\d+\.\d+)/")
GLOBAL_TIMEOUT = 900
PAGE_DWELL = 10
SEARCH_KEYWORDS = ("2026", "演唱会", "音乐会")
BUY_BUTTON_TEXTS = ("立即预订", "立即购买", "立即抢票", "选座购买", "立即预定", "立即购票")
FAV_SELECTORS = (
    'text=/想看/', '[class*="collect"]', '[class*="favor"]', '[class*="heart"]',
    'i[class*="xin"]', '[aria-label*="收藏"]', '[aria-label*="想看"]',
)
FAV_LIST_URLS = (
    "https://m.damai.cn/shows/favorite.html",
    "https://m.damai.cn/mine/favorite",
    "https://m.damai.cn/shows/favor.html",
)


def load_cookies() -> list[dict]:
    raw = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    out: list[dict] = []
    for name, value in raw.items():
        for domain in (".damai.cn", ".taobao.com"):
            out.append({"name": name, "value": str(value), "domain": domain, "path": "/",
                        "httpOnly": False, "secure": True, "sameSite": "None"})
    return out


def _scan_onsale(body: str) -> list[str]:
    """从 JSON body 里挖售中 itemId：按 saleStatus 定位窗口，失败则退化全取。"""
    ids: list[str] = []
    for m in re.finditer(r'"saleStatus"\s*:\s*"?([\w一-龥]+)"?', body):
        if m.group(1).lower() not in {"onsale", "2", "在售", "1"}:
            continue
        window = body[max(0, m.start() - 400):min(len(body), m.end() + 400)]
        ids.extend(im.group(1) for im in re.finditer(r'"itemId"\s*:\s*"?(\d{6,})"?', window))
    if not ids:
        ids = [m.group(1) for m in re.finditer(r'"itemId"\s*:\s*"?(\d{6,})"?', body)][:10]
    return list(dict.fromkeys(ids))[:5]


async def find_onsale_items(page, response_bodies: dict[str, str]) -> list[str]:
    urls = ["https://m.damai.cn/"] + [f"https://m.damai.cn/shows/search.html?keyword={kw}" for kw in SEARCH_KEYWORDS]
    item_ids: list[str] = []
    for url in urls:
        print(f"[stage1] 访问 {url}", flush=True)
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
        for body in list(response_bodies.values()):
            for iid in _scan_onsale(body):
                if iid not in item_ids:
                    item_ids.append(iid)
        if len(item_ids) >= 5:
            break
    print(f"[stage1] 售中候选: {item_ids[:5]}", flush=True)
    return item_ids[:5]


async def _try_click_buy(page, current_label: dict) -> bool:
    for btn in BUY_BUTTON_TEXTS:
        try:
            loc = page.get_by_text(btn, exact=False).first
            if await loc.count() == 0:
                continue
            try:
                if not await loc.is_enabled(timeout=1_000):
                    continue
            except Exception:
                pass
            print(f"  [点击] {btn}", flush=True)
            current_label["v"] = "build"
            await loc.click(timeout=5_000)
            await asyncio.sleep(PAGE_DWELL)
            cur = page.url
            print(f"    -> url: {cur}", flush=True)
            if re.search(r"(confirmOrder|buildOrder|trade|order|pay)", cur, re.I):
                await asyncio.sleep(PAGE_DWELL)
                return True
        except Exception as exc:
            print(f"  ! {btn} 失败: {exc}", flush=True)
    return False


async def try_trigger_build(page, current_label: dict, item_ids: list[str]) -> str | None:
    current_label["v"] = "detail"
    for iid in item_ids:
        for path in ("/shows/item.html", "/damai/detail/item.html"):
            url = f"https://m.damai.cn{path}?itemId={iid}"
            print(f"[stage2] 详情页 {url}", flush=True)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception as exc:
                print(f"  ! goto 失败: {exc}", flush=True)
                continue
            await asyncio.sleep(PAGE_DWELL)
            if await _try_click_buy(page, current_label):
                return iid
    print("[stage2] 未能触发 build", flush=True)
    return None


async def _fav_strategy_list(page) -> bool:
    for url in FAV_LIST_URLS:
        print(f"  goto {url}", flush=True)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        except Exception as exc:
            print(f"    ! goto 失败: {exc}", flush=True)
            continue
        await asyncio.sleep(PAGE_DWELL)
        final = page.url
        try:
            title = await page.title()
        except Exception:
            title = ""
        print(f"    -> {final} title={title!r}", flush=True)
        if "favor" in final.lower() or "收藏" in title or "想看" in title:
            return True
    return False


_MINE_JS = """() => {
  const kws = ['想看','我的想看','收藏','我的收藏'], out = [];
  document.querySelectorAll('a,div,span,li,button').forEach(el => {
    const t = (el.textContent || '').trim();
    if (t.length > 15) return;
    for (const k of kws) if (t === k || t.endsWith(k)) { out.push({kw:k,tag:el.tagName,text:t}); break; }
  });
  return out.slice(0, 10);
}"""


async def _fav_strategy_mine(page) -> bool:
    try:
        await page.goto("https://m.damai.cn/shows/mine.html", wait_until="domcontentloaded", timeout=20_000)
        await asyncio.sleep(PAGE_DWELL)
        hits = await page.evaluate(_MINE_JS)
    except Exception as exc:
        print(f"  ! mine 遍历失败: {exc}", flush=True)
        return False
    print(f"  命中 {len(hits)}: {hits}", flush=True)
    for h in hits:
        try:
            loc = page.get_by_text(h["text"], exact=True).first
            if await loc.count() == 0:
                continue
            print(f"  [点击] {h['text']}", flush=True)
            await loc.click(timeout=5_000)
            await asyncio.sleep(PAGE_DWELL)
            final = page.url
            print(f"    -> {final}", flush=True)
            if "favor" in final.lower() or final != "https://m.damai.cn/shows/mine.html":
                return True
        except Exception as exc:
            print(f"  ! 点击 {h.get('text')} 失败: {exc}", flush=True)
    return False


async def _fav_strategy_detail(page, item_ids: list[str]) -> bool:
    if not item_ids:
        return False
    url = f"https://m.damai.cn/shows/item.html?itemId={item_ids[0]}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as exc:
        print(f"  ! goto 失败: {exc}", flush=True)
        return False
    await asyncio.sleep(PAGE_DWELL)
    for sel in FAV_SELECTORS:
        try:
            loc = page.locator(sel).first
            if await loc.count() == 0:
                continue
            print(f"  [点击] selector={sel}", flush=True)
            await loc.click(timeout=5_000)
            await asyncio.sleep(6)
            return True
        except Exception as exc:
            print(f"  ! {sel} 失败: {exc}", flush=True)
    return False


async def try_capture_favorites(page, current_label: dict, item_ids: list[str]) -> bool:
    current_label["v"] = "favorites"
    print("[stage3-B] 直接访问收藏列表候选页", flush=True)
    if await _fav_strategy_list(page):
        return True
    print("[stage3-C] mine 页遍历找收藏入口", flush=True)
    if await _fav_strategy_mine(page):
        return True
    print("[stage3-A] 详情页点击想看按钮（会真实添加收藏）", flush=True)
    return await _fav_strategy_detail(page, item_ids)


async def run() -> None:
    from camoufox.async_api import AsyncCamoufox

    findings: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set[tuple[str, str]]] = defaultdict(set)
    response_bodies: dict[str, str] = {}
    current_label = {"v": "init"}

    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(viewport={"width": 1280, "height": 860})
        await context.add_cookies(load_cookies())

        def on_request(req) -> None:
            url = req.url
            if not MTOP_HOST_RE.search(url):
                return
            m = MTOP_RE.search(url)
            if not m:
                return
            key = (m.group(1), m.group(2))
            label = current_label["v"]
            if key in seen[label]:
                return
            seen[label].add(key)
            parsed = urlparse(url)
            findings[label].append({
                "api": key[0], "version": key[1], "method": req.method,
                "host": parsed.netloc,
                "data_preview": parse_qs(parsed.query).get("data", [""])[0][:200],
            })

        async def on_response(resp) -> None:
            if not MTOP_HOST_RE.search(resp.url) or not MTOP_RE.search(resp.url):
                return
            try:
                response_bodies[resp.url] = (await resp.text())[:8000]
            except Exception:
                pass

        context.on("request", on_request)
        context.on("response", lambda r: asyncio.create_task(on_response(r)))

        page = await context.new_page()

        current_label["v"] = "search_home"
        item_ids = await find_onsale_items(page, response_bodies)
        if item_ids:
            triggered = await try_trigger_build(page, current_label, item_ids)
            if triggered:
                print(f"[stage2] 成功触发 build (itemId={triggered})", flush=True)
        ok = await try_capture_favorites(page, current_label, item_ids)
        print(f"[stage3] favorites 结果: {ok}", flush=True)

        await context.close()

    print("\n" + "=" * 60 + "\n抓取结果汇总 (v2)\n" + "=" * 60)
    all_apis: set[tuple[str, str]] = set()
    for label, items in findings.items():
        if not items:
            continue
        print(f"\n### {label}")
        for it in items:
            all_apis.add((it["api"], it["version"]))
            print(f"  - {it['api']} / {it['version']}  [{it['method']}]")
            if it["data_preview"]:
                print(f"    data: {it['data_preview']}")
    print("\n### 全部唯一 api")
    for api, ver in sorted(all_apis):
        print(f"  {api} / {ver}")


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(run(), timeout=GLOBAL_TIMEOUT))
    except asyncio.TimeoutError:
        print("[timeout] 脚本整体超时退出", file=sys.stderr)
        sys.exit(1)
