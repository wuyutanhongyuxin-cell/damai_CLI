from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Show


def _parse_time(s: str | None) -> datetime | None:
    """宽容解析 ISO 8601 / 时间戳字符串；解析失败返回 None。"""
    if not s:
        return None
    # 尝试 Unix 时间戳（毫秒或秒）
    try:
        ts = float(s)
        ts = ts / 1000 if ts > 1e10 else ts
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        pass
    # 尝试 ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return None


def _normalize(values: list[float]) -> list[float]:
    """Min-max 归一化；全相同时统一返回 1.0。"""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _time_proximity_scores(shows: list[Show], now: datetime) -> list[float]:
    """计算每场演出的时间接近度评分（距今越近分越高）。"""
    secs: list[float] = []
    for s in shows:
        dt = _parse_time(s.start_time)
        secs.append(float("inf") if dt is None else abs((dt - now).total_seconds()))
    finite = [v for v in secs if v != float("inf")]
    if not finite:
        return [0.5] * len(shows)
    lo, hi = min(finite), max(finite)
    scores: list[float] = []
    for v in secs:
        if v == float("inf"):
            scores.append(0.0)
        elif hi == lo:
            scores.append(1.0)
        else:
            scores.append(1.0 - (v - lo) / (hi - lo))
    return scores


def rank_shows(
    shows: list[Show],
    *,
    w_hotness: float = 0.3,
    w_time: float = 0.2,
    w_price: float = 0.1,
) -> list[Show]:
    """综合打分排序：hotness + time_proximity + price_affordability，总分降序。
    hotness 代理：price_max；price_affordability：price_min 反向。
    """
    if not shows:
        return []
    now = datetime.now(tz=timezone.utc)
    hotness = _normalize([float(s.price_max or 0) for s in shows])
    time_sc = _time_proximity_scores(shows, now)
    afford = [1.0 - v for v in _normalize([float(s.price_min or 0) for s in shows])]
    scored = [
        (w_hotness * hotness[i] + w_time * time_sc[i] + w_price * afford[i], s)
        for i, s in enumerate(shows)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]


def filter_by_city(shows: list[Show], city: str) -> list[Show]:
    """按城市名过滤（不区分大小写，部分匹配）。"""
    city_lower = city.lower()
    return [s for s in shows if s.city and city_lower in s.city.lower()]


def filter_by_status(shows: list[Show], status: str) -> list[Show]:
    """按状态精确过滤（on_sale / pre_sale / ended）。"""
    return [s for s in shows if s.status == status]


def filter_by_category(shows: list[Show], category: str) -> list[Show]:
    """按分类过滤（不区分大小写，部分匹配）。"""
    cat_lower = category.lower()
    return [s for s in shows if s.category and cat_lower in s.category.lower()]


def filter_by_price(
    shows: list[Show],
    *,
    min_price: float | None = None,
    max_price: float | None = None,
) -> list[Show]:
    """按价格区间过滤；以 price_min 为下界、price_max 为上界对比。"""
    result = []
    for s in shows:
        if min_price is not None and (s.price_max is None or s.price_max < min_price):
            continue
        if max_price is not None and (s.price_min is None or s.price_min > max_price):
            continue
        result.append(s)
    return result
