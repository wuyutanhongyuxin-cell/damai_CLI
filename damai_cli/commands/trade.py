from __future__ import annotations

import json
import sys
import time

import click

from ..config import CACHE_DIR
from ..exceptions import (
    InvalidInput,
    IpBlocked,
    ItemSoldOut,
    NeedSlideCaptcha,
    RealNameRequired,
)
from ..output import ok
from ._common import get_client, run_command

# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _warn_write() -> None:
    """在 stderr 打印红色风险提示，每次写操作前必须调用。"""
    click.echo(
        click.style("[risk] 发送写操作到大麦服务器；违规使用自负封号风险", fg="red"),
        err=True,
    )


def _guard_captcha(fn, *args, **kwargs):
    """调用 fn；遇滑块/IP封锁立即 emit err 并 sys.exit(1)。"""
    from ..output import emit, err

    try:
        return fn(*args, **kwargs)
    except NeedSlideCaptcha as e:
        emit(err(e.code, "遭遇滑块验证，请改用官方大麦 App"))
        sys.exit(1)
    except IpBlocked as e:
        emit(err(e.code, "IP 被封锁，请改用官方大麦 App"))
        sys.exit(1)


def _save_build_cache(token: str, item_id: str) -> None:
    """把 build_token 写到 CACHE_DIR/last_build.json。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"token": token, "item_id": item_id, "timestamp": int(time.time())}
    (CACHE_DIR / "last_build.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _build_request(c, item_id: str, perform_id: str, sku_id: str,
                   viewer_id: str, count: int) -> dict:
    """调 mtop.trade.order.build.h5 并返回上游 data。"""
    data = {
        "itemId": item_id,
        "performId": perform_id,
        "skuId": sku_id,
        "buyerId": viewer_id,
        "quantity": count,
    }
    return _guard_captcha(c.request,
                         "mtop.trade.order.build.h5", "1.0", data,
                         need_login=True)


def _submit_request(c, build_token: str) -> dict:
    """调 mtop.trade.order.create.h5 并返回上游 data。"""
    return _guard_captcha(c.request,
                         "mtop.trade.order.create.h5", "1.0",
                         {"buildToken": build_token}, need_login=True)


def _pay_url_request(c, order_id: str) -> dict:
    """调 mtop.trade.order.pay.getpayurl 并返回上游 data。"""
    return _guard_captcha(c.request,
                         "mtop.trade.order.pay.getpayurl", "1.0",
                         {"orderId": order_id}, need_login=True)


def _extract_build_result(raw: dict, item_id: str) -> dict:
    """从 build 响应中提取 token + 预览字段并缓存。"""
    token = raw.get("buildToken") or raw.get("token") or ""
    preview = {
        "total_fee": raw.get("totalFee") or raw.get("total_fee"),
        "real_name": raw.get("realName") or raw.get("buyerName"),
        "sku_desc": raw.get("skuDesc") or raw.get("skuName"),
    }
    if token:
        _save_build_cache(token, item_id)
    return {"build_token": token, "preview": preview}


def _extract_submit_result(raw: dict) -> dict:
    """从 create 响应中提取 order_id + pay_url；处理实名/售罄异常。"""
    ret_msg = (raw.get("retMsg") or "").lower()
    if "realname" in ret_msg or "实名" in ret_msg:
        raise RealNameRequired("实名认证未完成，请在大麦 App 完成实名")
    if "sold_out" in ret_msg or "售罄" in ret_msg:
        raise ItemSoldOut("票已售罄")
    return {
        "order_id": raw.get("orderId") or raw.get("order_id") or "",
        "pay_url": raw.get("payUrl") or raw.get("pay_url") or "",
    }


# ── 命令注册 ──────────────────────────────────────────────────────────────────

def register(cli: click.Group) -> None:

    @cli.command("build")
    @click.argument("item_id")
    @click.option("--perform", "perform_id", required=True, help="场次 ID")
    @click.option("--sku", "sku_id", required=True, help="票档 ID")
    @click.option("--viewer", "viewer_id", required=True, help="观演人数字 ID")
    @click.option("--count", default=1, show_default=True, type=int, help="购票数量")
    @click.option("--no-dry-run", "no_dry_run", is_flag=True, default=False,
                  help="仅影响 submit 阶段说明；build 本身始终发送")
    @run_command
    def build_cmd(item_id, perform_id, sku_id, viewer_id, count, no_dry_run):
        # viewer_id 只接受纯数字，防止 name 模糊匹配误选
        if not viewer_id.isdigit():
            raise InvalidInput("viewer_id 必须为数字 ID，不支持姓名模糊匹配")
        click.echo(
            f"[dry-run] build payload: itemId={item_id} performId={perform_id} "
            f"skuId={sku_id} buyerId={viewer_id} quantity={count}",
            err=True,
        )
        _warn_write()
        with get_client(need_login=True) as c:
            raw = _build_request(c, item_id, perform_id, sku_id, viewer_id, count)
        result = _extract_build_result(raw, item_id)
        return ok(result)

    @cli.command("submit")
    @click.argument("build_token")
    @click.option("--i-understand-risk", "confirmed", is_flag=True, default=False,
                  help="确认风险后才真实下单")
    @run_command
    def submit_cmd(build_token, confirmed):
        # 无确认 flag → dry-run，打印 payload 和支付 URL 预览后返回
        if not confirmed:
            payload_preview = {"buildToken": build_token}
            click.echo(
                f"[dry-run] 将发送: mtop.trade.order.create.h5 payload={payload_preview}",
                err=True,
            )
            click.echo("[dry-run] 支付 URL 预览：（需真实下单后获取）", err=True)
            return ok({"dry_run": True, "build_token": build_token})
        _warn_write()
        with get_client(need_login=True) as c:
            raw = _submit_request(c, build_token)
        result = _extract_submit_result(raw)
        return ok(result)

    @cli.command("buy")
    @click.argument("item_id")
    @click.option("--perform", "perform_id", required=True)
    @click.option("--sku", "sku_id", required=True)
    @click.option("--viewer", "viewer_id", required=True)
    @click.option("--count", default=1, show_default=True, type=int)
    @click.option("--auto-submit", "auto_submit", is_flag=True, default=False)
    @click.option("--i-understand-risk", "confirmed", is_flag=True, default=False)
    @run_command
    def buy_cmd(item_id, perform_id, sku_id, viewer_id, count,
                auto_submit, confirmed):
        if not viewer_id.isdigit():
            raise InvalidInput("viewer_id 必须为数字 ID，不支持姓名模糊匹配")
        # auto-submit 没有风险确认 flag 时拒绝
        if auto_submit and not confirmed:
            raise InvalidInput("--auto-submit 必须同时带 --i-understand-risk")
        click.echo(
            f"[dry-run] build payload: itemId={item_id} performId={perform_id} "
            f"skuId={sku_id} buyerId={viewer_id} quantity={count}",
            err=True,
        )
        _warn_write()
        with get_client(need_login=True) as c:
            raw_build = _build_request(c, item_id, perform_id, sku_id, viewer_id, count)
            build_result = _extract_build_result(raw_build, item_id)
            if not auto_submit:
                return ok({**build_result, "submitted": False})
            raw_submit = _submit_request(c, build_result["build_token"])
        submit_result = _extract_submit_result(raw_submit)
        return ok({**build_result, "submitted": True, **submit_result})

    @cli.command("pay-url")
    @click.argument("order_id")
    @run_command
    def pay_url_cmd(order_id):
        with get_client(need_login=True) as c:
            raw = _pay_url_request(c, order_id)
        return ok({"order_id": order_id, "pay_url": raw.get("payUrl") or raw.get("pay_url") or ""})
