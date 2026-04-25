from __future__ import annotations

import random
import time

import click

from ._common import get_client

# 轮询时随机 jitter 范围（秒）
_JITTER = 5

# 视为"已开售"的 status 值
_ON_SALE_STATUSES = {"on_sale", "onsale", "forsale", "sale"}

# 视为可售的 SKU stock_status 值
_AVAILABLE_STOCK = {"available", "on_sale", "forsale"}


def _has_available_sku(raw: dict) -> bool:
    """检查 detail 响应里是否存在可售 SKU。"""
    skus = (
        raw.get("skuList")
        or raw.get("skus")
        or raw.get("performList", [{}])[0].get("skuList", [])
        if raw.get("performList")
        else []
    )
    for sku in skus:
        st = str(sku.get("stockStatus") or sku.get("saleStatus") or "").lower()
        if st in _AVAILABLE_STOCK:
            return True
    return False


def _parse_status(raw: dict) -> str | None:
    """从 detail 响应中提取状态字符串。"""
    return (
        raw.get("saleStatus")
        or raw.get("status")
        or raw.get("itemStatus")
    )


def _notify(item_id: str, use_notify: bool, message: str) -> None:
    """向用户推送开票通知（弹窗 + 打印）。"""
    print(f"[大麦开票提醒] {message}")
    if not use_notify:
        return
    try:
        from plyer import notification  # type: ignore
        notification.notify(
            title="大麦开票提醒",
            message=message,
            timeout=10,
        )
    except Exception:
        # plyer 不可用时静默降级
        pass


def _poll_once(client, item_id: str, perform_id: str | None) -> dict:
    """调一次 detail API，返回原始 data 字典。"""
    params: dict = {"itemId": item_id}
    if perform_id:
        params["performId"] = perform_id
    return client.request(
        "mtop.damai.item.detail.getdetail",
        "1.0",
        data=params,
        need_login=False,
    )


def _check_once(client, item_id: str, perform_id: str | None, n: int) -> bool:
    """执行一次检查，返回 True 表示已开售。请求失败返回 False。"""
    try:
        raw = _poll_once(client, item_id, perform_id)
    except Exception as exc:
        print(f"[第{n}次] 请求失败：{exc}")
        return False
    status = str(_parse_status(raw) or "").lower()
    avail = _has_available_sku(raw)
    if status in _ON_SALE_STATUSES or avail:
        return True
    print(f"[第{n}次] status={status or '未知'}，尚未开售")
    return False


def _run_loop(
    item_id: str,
    perform_id: str | None,
    interval: int,
    use_notify: bool,
    max_checks: int,
) -> None:
    """执行轮询主循环，开售或达到上限后返回。"""
    checks = 0
    triggered = False
    print(f"开始监控 item_id={item_id}，间隔 {interval}±{_JITTER}s，最多 {max_checks} 次")
    try:
        with get_client(need_login=False) as client:
            while checks < max_checks:
                checks += 1
                if _check_once(client, item_id, perform_id, checks):
                    msg = f"item {item_id} 已开票"
                    _notify(item_id, use_notify, msg)
                    triggered = True
                    break
                _sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        _print_summary(checks, triggered, item_id)


def register(cli: click.Group) -> None:

    @cli.command(name="track")
    @click.argument("item_id")
    @click.option("--perform", "perform_id", default=None, help="场次 ID")
    @click.option("--interval", default=30, show_default=True, help="轮询间隔（秒）")
    @click.option("--notify", "use_notify", is_flag=True, default=True,
                  help="开票时弹系统通知（默认开启）")
    @click.option("--max-checks", default=2880, show_default=True,
                  help="最大检查次数（默认 2880，约 24h）")
    def track(
        item_id: str,
        perform_id: str | None,
        interval: int,
        use_notify: bool,
        max_checks: int,
    ) -> None:
        """监控演出开票状态，开售时弹通知并退出。"""
        _run_loop(item_id, perform_id, interval, use_notify, max_checks)


def _sleep(interval: int) -> None:
    """带 jitter 的等待，避免固定频率被识别为爬虫。"""
    jitter = random.uniform(-_JITTER, _JITTER)
    time.sleep(max(1, interval + jitter))


def _print_summary(checks: int, triggered: bool, item_id: str) -> None:
    """退出时打印本次监控摘要。"""
    result = "已触发开票通知" if triggered else "未检测到开票"
    print(f"\n[监控结束] item_id={item_id} 共检查 {checks} 次，{result}")
