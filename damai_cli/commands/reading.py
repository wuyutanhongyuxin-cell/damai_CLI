from __future__ import annotations

from dataclasses import asdict

import click

from ._common import run_command, get_client
from ..models import Show, Artist, Venue
from ..filter import rank_shows

# 静态分类表（大麦主流演出类型）
_STATIC_CATEGORIES = [
    "话剧",
    "演唱会",
    "音乐会",
    "体育",
    "展览",
    "舞蹈芭蕾",
    "亲子",
    "曲苑杂坛",
]


def _flatten_detail(raw: dict) -> dict:
    """detail 响应（含 item/venue/price/guide/itemPics 嵌套）扁平化为 Show.from_dict 可吃的 dict。"""
    item = raw.get("item") or {}
    venue = raw.get("venue") or {}
    price = raw.get("price") or {}
    guide = raw.get("guide") or {}
    pics = (item.get("itemPics") or {}).get("itemPicList") or []
    range_str = str(price.get("range") or "")
    low = range_str.split("-", 1)[0] if "-" in range_str else ""
    return {
        **item,
        "venueName": venue.get("venueName") or venue.get("name"),
        "guideCategoryName": guide.get("guideCat"),
        "priceLow": low if low.isdigit() else None,
        "posterUrl": pics[0].get("picUrl") if pics else None,
    }


def register(cli: click.Group) -> None:

    @cli.command(name="search")
    @click.argument("keyword", required=False, default="")
    @click.option("--limit", type=int, default=20, show_default=True, help="返回条数")
    @click.option("--city", default="852", show_default=True, help="大麦 cityId")
    @click.option("--category-id", "category_id", type=int, default=0,
                  show_default=True, help="分类 id，0=全部")
    @run_command
    def search(keyword, limit, city, category_id):
        """演出查询。keyword 非空时在客户端做 name substring 过滤。"""
        # 大麦服务端搜索接口暂未抓到真实字段名；此处复用 list 接口 + 本地过滤
        fetch_size = max(limit * 3, 30) if keyword else limit
        params = {
            "cityId": city, "distanceCityId": city, "pageIndex": 0,
            "pageSize": fetch_size, "categoryId": category_id, "dateType": 0,
            "option": 31, "sourceType": 21, "returnItemOption": 4,
        }
        with get_client() as c:
            raw = c.request("mtop.damai.wireless.search.search", "1.0", params)
        items = raw.get("projectInfo") or []
        if keyword:
            kw = keyword.strip().lower()
            items = [x for x in items if kw in str(x.get("name") or "").lower()]
        shows = rank_shows([Show.from_dict(x) for x in items])[:limit]
        return {"shows": [asdict(s) for s in shows]}

    @cli.command(name="show")
    @click.argument("item_id")
    @run_command
    def show_detail(item_id):
        """演出详情。返回 show + buyButton（部分演出 H5 禁购）。"""
        with get_client() as c:
            raw = c.request(
                "mtop.damai.item.detail.getdetail", "1.0", {"itemId": item_id}
            )
        show = Show.from_dict(_flatten_detail(raw))
        return {"show": asdict(show), "buyButton": raw.get("buyButton") or {}}

    @cli.command(name="hot")
    @click.option("--city", default="852", show_default=True, help="大麦 cityId（数字字符串）")
    @run_command
    def hot(city):
        """热门演出广播。"""
        with get_client() as c:
            raw = c.request("mtop.damai.wireless.search.broadcast.home", "1.0", {"cityId": city})
        shows = [Show.from_dict(x) for x in raw.get("projects", [])]
        top = raw.get("top")
        if isinstance(top, dict) and top:
            shows.insert(0, Show.from_dict(top))
        shows = rank_shows(shows)
        return {"shows": [asdict(s) for s in shows]}

    @cli.command(name="calendar")
    @click.option("--city", default="852", show_default=True, help="大麦 cityId")
    @click.option("--limit", type=int, default=15, show_default=True, help="返回条数")
    @click.option("--category-id", "category_id", type=int, default=0,
                  show_default=True, help="分类 id，0=全部")
    @run_command
    def calendar(city, limit, category_id):
        """近期演出列表（按城市+分类过滤）。"""
        params = {
            "currentCityId": city, "cityOption": 1, "pageIndex": 1,
            "pageSize": limit, "sortType": 3, "categoryId": category_id,
            "returnItemOption": 4, "dateType": 0,
        }
        with get_client() as c:
            raw = c.request("mtop.damai.wireless.search.project.classify", "1.0", params)
        shows = rank_shows([Show.from_dict(x) for x in raw.get("nearByCity") or []])
        return {"shows": [asdict(s) for s in shows]}

    @cli.command(name="artist")
    @click.argument("name")
    @run_command
    def artist(name):
        # 艺人信息查询
        with get_client() as c:
            raw = c.request(
                "mtop.damai.wireless.channel.artiste", "1.0", {"artistName": name}
            )
        art = Artist.from_dict(raw)
        return {"artist": asdict(art)}

    @cli.command(name="venue")
    @click.argument("venue_id")
    @run_command
    def venue(venue_id):
        # 场馆详情
        with get_client() as c:
            # TODO pending capture: venue 未抓到实测 api
            raw = c.request(
                "mtop.damai.mdata.venue.getvenuedetail", "1.0", {"venueId": venue_id}
            )
        v = Venue.from_dict(raw)
        return {"venue": asdict(v)}

    @cli.command(name="category")
    @run_command
    def category():
        """拉大麦动态分类列表（演唱会/话剧/音乐节等）。"""
        with get_client() as c:
            raw = c.request(
                "mtop.damai.wireless.search.cms.category.get",
                "2.0",
                {"apiVersion": "3.1"},
            )
        items = raw.get("data") or []
        cats = [{"name": it.get("name"), "pattern": it.get("patternName"),
                 "args": it.get("args")} for it in items if it.get("name")]
        return {"categories": cats, "static": _STATIC_CATEGORIES}
