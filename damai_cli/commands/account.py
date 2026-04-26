from __future__ import annotations

import re
from dataclasses import asdict

import click

from ..models import Order, Show, Viewer
from ..output import ok
from ._common import get_client, run_command

# 证件号打码：保留前 4 后 4，中间全替换为 *
_CERT_RE = re.compile(r"^(.{4})(.+)(.{4})$")


def _mask_cert(raw: str | None) -> str | None:
    """对原始证件号做脱敏，长度 < 8 时原样返回。"""
    if not raw:
        return raw
    m = _CERT_RE.match(raw)
    if not m:
        return raw
    return m.group(1) + "*" * len(m.group(2)) + m.group(3)


def _build_viewer(raw: dict) -> Viewer:
    """从原始字典提取 Viewer，并对 cert_no 做打码。"""
    # 尝试从多个候选字段取原始证件号
    cert_raw = (
        raw.get("certNo")
        or raw.get("cardNo")
        or raw.get("cert_no")
        or raw.get("certNoMasked")
        or raw.get("cert_no_masked")
    )
    v = Viewer.from_dict(raw)
    # 用打码值覆盖 from_dict 里可能已有的值
    object.__setattr__(v, "cert_no_masked", _mask_cert(cert_raw))
    return v


def register(cli: click.Group) -> None:

    @cli.command(name="favorites")
    @run_command
    def favorites() -> dict:
        """查看我的收藏演出。"""
        with get_client(need_login=True) as c:
            # TODO pending capture: favorites 未抓到实测 api
            raw = c.request(
                "mtop.damai.user.myfavorite",
                "1.0",
                need_login=True,
            )
        items = raw.get("result") or raw.get("data") or raw.get("list") or []
        shows = [asdict(Show.from_dict(x)) for x in items]
        return ok({"shows": shows, "total": len(shows)})

    @cli.command(name="orders")
    @click.option("--status", type=click.Choice(["pending", "paid", "refunded"]),
                  default=None, help="订单状态（映射待抓到含订单的账户才能验证）")
    @run_command
    def orders(status: str | None) -> dict:
        """查看我的订单列表。"""
        # queryType="0" = 全部；pageNum/pageSize/bindUserIdList/queryOrderType 全部必填
        params = {
            "queryType": "0", "queryOrderType": 1,
            "pageNum": 1, "pageSize": 10, "bindUserIdList": "[]",
        }
        with get_client(need_login=True) as c:
            raw = c.request(
                "mtop.damai.wireless.order.orderlist", "2.0",
                data=params, need_login=True,
            )
        items = raw.get("orderList") or raw.get("orders") or raw.get("list") or []
        order_list = [asdict(Order.from_dict(x)) for x in items]
        return ok({"orders": order_list, "total": len(order_list)})

    @cli.command(name="viewers")
    @run_command
    def viewers() -> dict:
        """查看账户下已绑定的实名观演人。"""
        with get_client(need_login=True) as c:
            raw = c.request(
                "mtop.damai.wireless.user.customerlist.get", "2.0",
                data={"customerType": "default"}, need_login=True,
            )
        items = raw.get("customerList") or raw.get("list") or raw.get("result") or []
        viewer_list = [asdict(_build_viewer(x)) for x in items]
        return ok({"viewers": viewer_list, "total": len(viewer_list)})
