from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# 全局 Console；stderr=False 输出到 stdout
_console = Console()

# data 中含列表的业务字段，触发 Table 渲染
_LIST_KEYS = ("shows", "orders", "viewers", "favorites")


def render_table(rows: list[dict], columns: list[str], title: str = "") -> None:
    # 渲染带标题的 rich Table
    tbl = Table(title=title or None, show_lines=True)
    for col in columns:
        tbl.add_column(col, overflow="fold")
    for row in rows:
        tbl.add_row(*[str(row.get(c, "")) for c in columns])
    _console.print(tbl)


def render_detail(obj: dict, title: str = "") -> None:
    # 用 Panel 展示单个对象（JSON 格式化）
    body = json.dumps(obj, ensure_ascii=False, indent=2)
    _console.print(Panel(body, title=title or None, expand=False))


def render_list(items: list[str]) -> None:
    # 简单逐行输出字符串列表
    for item in items:
        _console.print(item)


def _extract_list_field(data: dict) -> tuple[str, list[dict]] | None:
    # 从 dict 中找第一个命中 _LIST_KEYS 的列表字段
    for key in _LIST_KEYS:
        val = data.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return key, val
    return None


def _render_list_of_dicts(rows: list[dict], title: str = "") -> None:
    # 取前 5 个 key 作为列名
    columns = list(rows[0].keys())[:5]
    render_table(rows, columns, title=title)


def render_envelope_rich(envelope: dict) -> None:
    # 按 envelope 状态和 data 类型分派渲染方式
    if not envelope.get("ok"):
        error = envelope.get("error", {})
        code = error.get("code", "unknown")
        message = error.get("message", "")
        body = f"[bold]{code}[/bold]\n{message}"
        _console.print(Panel(body, title="Error", style="red", expand=False))
        return

    data = envelope.get("data")

    # data 是列表且元素是 dict
    if isinstance(data, list) and data and isinstance(data[0], dict):
        _render_list_of_dicts(data)
        return

    # data 是 dict：检查是否含业务列表字段
    if isinstance(data, dict):
        hit = _extract_list_field(data)
        if hit:
            field_name, rows = hit
            _render_list_of_dicts(rows, title=field_name)
            return
        # 普通 dict → Panel JSON
        render_detail(data)
        return

    # 兜底：直接 Panel 输出
    body = json.dumps(data, ensure_ascii=False, indent=2)
    _console.print(Panel(body, expand=False))
