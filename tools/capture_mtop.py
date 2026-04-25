"""用 camoufox 复用本地 cookie 自动访问关键页面，抓取所有 mtop.damai.cn 请求。

跑法：python tools/capture_mtop.py
输出：按页面分组的 api 列表（去重）+ 请求 method + 关键 query 参数。
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COOKIES_PATH = Path.home() / ".damai-cli" / "cookies.json"

PAGES: list[tuple[str, str]] = [
    ("home_h5", "https://m.damai.cn/"),
    ("category", "https://m.damai.cn/shows/category.html"),
    ("mine", "https://m.damai.cn/shows/mine.html"),
]

# 这批 URL 在 mine 页挖到真实链接后动态追加
DYNAMIC_AFTER_MINE = True

# mtop 网关可能出现在这几个域：damai 自己的 + taobao 的 + 阿里 acs
MTOP_HOST_RE = re.compile(r"(mtop\.damai\.cn|h5api\.m\.taobao\.com|acs\.m\.taobao\.com)")
MTOP_RE = re.compile(r"/h5/(mtop\.[\w.]+)/(\d+\.\d+)/")
PAGE_DWELL = 10  # seconds
GLOBAL_TIMEOUT = 600


def load_cookies() -> list[dict]:
    """把 cookies.json 转成 playwright 可用格式，同时塞 .damai.cn 和 .taobao.com 两个域。

    跨域需要 sameSite=None + secure=True，否则 h5 页面 fetch mtop 时浏览器不带 cookie。
    """
    raw = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    out: list[dict] = []
    for name, value in raw.items():
        for domain in (".damai.cn", ".taobao.com"):
            out.append({
                "name": name,
                "value": str(value),
                "domain": domain,
                "path": "/",
                "httpOnly": False,
                "secure": True,
                "sameSite": "None",
            })
    return out


async def _extract_item_ids(response_bodies: dict) -> list[str]:
    """从已抓响应体中挖 itemId（大麦详情页参数）。"""
    ids: set[str] = set()
    patterns = [
        re.compile(r'"itemId"\s*:\s*"?(\d{6,})"?'),
        re.compile(r'"id"\s*:\s*"?(\d{8,})"?'),
        re.compile(r'itemId=(\d{6,})'),
    ]
    for body in response_bodies.values():
        if not body:
            continue
        for pat in patterns:
            for m in pat.finditer(body):
                ids.add(m.group(1))
                if len(ids) >= 5:
                    return list(ids)
    return list(ids)


async def run() -> None:
    from camoufox.async_api import AsyncCamoufox

    findings: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set[tuple[str, str]]] = defaultdict(set)
    response_bodies: dict[str, str] = {}
    current_page_label = {"v": "init"}

    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(viewport={"width": 1280, "height": 860})
        await context.add_cookies(load_cookies())

        def on_request(req):
            url = req.url
            if not MTOP_HOST_RE.search(url):
                return
            m = MTOP_RE.search(url)
            if not m:
                return
            api, ver = m.group(1), m.group(2)
            key = (api, ver)
            label = current_page_label["v"]
            if key in seen[label]:
                return
            seen[label].add(key)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            data_field = qs.get("data", [""])[0][:200]
            findings[label].append({
                "api": api,
                "version": ver,
                "method": req.method,
                "host": parsed.netloc,
                "data_preview": data_field,
            })

        async def on_response(resp):
            url = resp.url
            if not MTOP_HOST_RE.search(url):
                return
            m = MTOP_RE.search(url)
            if not m:
                return
            try:
                body = await resp.text()
                response_bodies[url] = body[:5000]  # 挖 itemId 用
            except Exception:
                pass

        context.on("request", on_request)
        context.on("response", lambda r: asyncio.create_task(on_response(r)))

        page = await context.new_page()
        for label, url in PAGES:
            current_page_label["v"] = label
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
            try:
                final_url = page.url
                title = await page.title()
                print(f"  -> final: {final_url}  title={title!r}", flush=True)
            except Exception:
                pass
            # mine 是 SPA：多等一会让 react 渲染，再用 playwright 的 locator click
            if label == "mine":
                await asyncio.sleep(8)
                # 保存 HTML 用于离线分析
                try:
                    html = await page.content()
                    (Path.cwd() / "mine_dump.html").write_text(html, encoding="utf-8")
                    # 挖带"订单/收藏/观演人"文字的元素（含父节点上下文）
                    hints = await page.evaluate("""() => {
                        const keywords = ['订单', '收藏', '观演人', '全部订单', '我的收藏'];
                        const hits = [];
                        document.querySelectorAll('*').forEach(el => {
                            const t = (el.textContent || '').trim();
                            if (t.length > 20) return;
                            for (const k of keywords) {
                                if (t === k || t.endsWith(k)) {
                                    hits.push({kw: k, tag: el.tagName, cls: el.className?.toString?.() || '', text: t});
                                    break;
                                }
                            }
                        });
                        return hits.slice(0, 30);
                    }""")
                    print(f"  [文本命中 {len(hints)}]", flush=True)
                    for h in hints:
                        print(f"    {h}", flush=True)
                except Exception as exc:
                    print(f"  ! mine 分析失败: {exc}", flush=True)

                # 用 playwright locator 直接点文本——大麦收藏叫"想看"
                for keyword, lab in [("订单", "orders"), ("想看", "favorites"), ("观演人", "viewers")]:
                    try:
                        loc = page.get_by_text(keyword, exact=False).first
                        if await loc.count() == 0:
                            print(f"    {keyword}: 未找到元素", flush=True)
                            continue
                        current_page_label["v"] = lab
                        print(f"  [点击] {keyword} (label={lab})", flush=True)
                        await loc.click(timeout=5_000)
                        await asyncio.sleep(6)
                        cur = page.url
                        print(f"    -> url: {cur}", flush=True)
                        # 回 mine 页，点下一个
                        await page.goto("https://m.damai.cn/shows/mine.html", wait_until="domcontentloaded", timeout=20_000)
                        await asyncio.sleep(4)
                        current_page_label["v"] = "mine"
                    except Exception as exc:
                        print(f"    ! 点击 {keyword} 失败: {exc}", flush=True)

        # 挖 itemId 访问详情页
        item_ids = await _extract_item_ids(response_bodies)
        print(f"\n[挖到 itemId] {item_ids}", flush=True)
        if item_ids:
            detail_url = f"https://m.damai.cn/damai/detail/item.html?itemId={item_ids[0]}"
            current_page_label["v"] = "detail"
            print(f"[访问] detail -> {detail_url}", flush=True)
            try:
                await page.goto(detail_url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(PAGE_DWELL)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)
            except Exception as exc:
                print(f"  ! detail 访问失败: {exc}", flush=True)

            # 从详情页点击"立即预订/立即购买/立即抢票"按钮跳建单页
            current_page_label["v"] = "build"
            for btn_text in ("立即预订", "立即购买", "立即抢票", "立即预定", "选座购买", "立即购票"):
                try:
                    loc = page.get_by_text(btn_text, exact=False).first
                    if await loc.count() == 0:
                        continue
                    print(f"[点击详情按钮] {btn_text}", flush=True)
                    await loc.click(timeout=5_000)
                    await asyncio.sleep(PAGE_DWELL)
                    cur = page.url
                    print(f"  -> url: {cur}", flush=True)
                    break
                except Exception as exc:
                    print(f"  ! {btn_text} 失败: {exc}", flush=True)

        await context.close()

    # 汇总
    print("\n" + "=" * 60)
    print("抓取结果汇总")
    print("=" * 60)
    for label, items in findings.items():
        if not items:
            continue
        print(f"\n### {label}")
        for it in items:
            print(f"  - {it['api']} / {it['version']}  [{it['method']}]")
            if it["data_preview"]:
                print(f"    data: {it['data_preview']}")

    # 全局去重 api 清单
    all_apis: set[tuple[str, str]] = set()
    for items in findings.values():
        for it in items:
            all_apis.add((it["api"], it["version"]))
    print("\n### 全部唯一 api")
    for api, ver in sorted(all_apis):
        print(f"  {api} / {ver}")


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(run(), timeout=GLOBAL_TIMEOUT))
    except asyncio.TimeoutError:
        print("[timeout] 脚本整体超时退出", file=sys.stderr)
        sys.exit(1)
