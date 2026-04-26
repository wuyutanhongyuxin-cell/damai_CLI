from __future__ import annotations

from dataclasses import dataclass


def _str(raw: dict, *keys: str) -> str | None:
    """按候选键顺序取第一个非空字符串，失败返回 None。"""
    for k in keys:
        v = raw.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _float(raw: dict, *keys: str) -> float | None:
    """按候选键顺序取第一个可转 float 的值。"""
    for k in keys:
        v = raw.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _int(raw: dict, *keys: str) -> int | None:
    """按候选键顺序取第一个可转 int 的值。"""
    for k in keys:
        v = raw.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return None


@dataclass(slots=True)
class Show:
    id: str
    name: str
    city: str | None = None
    venue: str | None = None
    category: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    status: str | None = None           # on_sale / pre_sale / ended
    start_time: str | None = None       # ISO 8601
    poster_url: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Show:
        # 字段覆盖 search.projectInfo / hot.projects / hot.top / detail.item 四种结构
        return cls(
            id=str(raw.get("itemId") or raw.get("id") or ""),
            name=_str(raw, "itemName", "showName", "title", "name") or "",
            city=_str(raw, "cityName", "city"),
            venue=_str(raw, "venueName", "venue", "showFieldName"),
            category=_str(raw, "guideCategoryName", "categoryName", "showTypeName", "category"),
            price_min=_float(raw, "priceLow", "priceMin", "price_min", "lowPrice"),
            price_max=_float(raw, "priceMax", "price_max", "highPrice"),
            status=_str(raw, "saleStatus", "projectStatus", "status"),
            start_time=_str(raw, "showTime", "startTime", "start_time", "showBeginTime",
                            "nearestPerformTime"),
            poster_url=_str(raw, "posterUrl", "verticalPic", "imgUrl", "poster_url", "image"),
        )


@dataclass(slots=True)
class Perform:
    perform_id: str
    show_id: str
    start_time: str | None = None
    venue: str | None = None
    seat_map_url: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Perform:
        return cls(
            perform_id=str(raw.get("performId") or raw.get("perform_id") or ""),
            show_id=str(raw.get("itemId") or raw.get("showId") or raw.get("show_id") or ""),
            start_time=_str(raw, "showTime", "startTime", "start_time"),
            venue=_str(raw, "venueName", "venue", "showFieldName"),
            seat_map_url=_str(raw, "seatMapUrl", "seat_map_url"),
        )


@dataclass(slots=True)
class Sku:
    sku_id: str
    perform_id: str
    price: float
    description: str | None = None
    stock_status: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Sku:
        return cls(
            sku_id=str(raw.get("skuId") or raw.get("sku_id") or ""),
            perform_id=str(raw.get("performId") or raw.get("perform_id") or ""),
            price=_float(raw, "price", "salePrice", "originalPrice") or 0.0,
            description=_str(raw, "desc", "description", "skuName", "name"),
            stock_status=_str(raw, "stockStatus", "stock_status", "saleStatus"),
        )


@dataclass(slots=True)
class Viewer:
    viewer_id: str
    name: str
    cert_type: str | None = None
    cert_no_masked: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Viewer:
        return cls(
            viewer_id=str(raw.get("viewerId") or raw.get("viewer_id") or raw.get("personId") or ""),
            name=_str(raw, "name", "realName", "viewerName") or "",
            cert_type=_str(raw, "certType", "cert_type", "cardType"),
            cert_no_masked=_str(raw, "certNoMasked", "cert_no_masked", "cardNo"),
        )


@dataclass(slots=True)
class Order:
    order_id: str
    show_name: str
    perform_time: str | None = None
    status: str | None = None
    total_fee: float | None = None
    pay_url: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Order:
        return cls(
            order_id=str(raw.get("orderId") or raw.get("order_id") or ""),
            show_name=_str(raw, "showName", "itemName", "show_name") or "",
            perform_time=_str(raw, "performTime", "showTime", "perform_time"),
            status=_str(raw, "orderStatus", "status"),
            total_fee=_float(raw, "totalFee", "total_fee", "totalAmount"),
            pay_url=_str(raw, "payUrl", "pay_url", "cashierUrl"),
        )


@dataclass(slots=True)
class Artist:
    id: str
    name: str
    follower_count: int | None = None
    upcoming_count: int | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Artist:
        return cls(
            id=str(raw.get("artistId") or raw.get("id") or ""),
            name=_str(raw, "artistName", "name") or "",
            follower_count=_int(raw, "followerCount", "follower_count", "fansCount"),
            upcoming_count=_int(raw, "upcomingCount", "upcoming_count", "showCount"),
        )


@dataclass(slots=True)
class Venue:
    id: str
    name: str
    city: str | None = None
    address: str | None = None
    capacity: int | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> Venue:
        return cls(
            id=str(raw.get("venueId") or raw.get("id") or ""),
            name=_str(raw, "venueName", "name") or "",
            city=_str(raw, "cityName", "city"),
            address=_str(raw, "address", "venueAddress"),
            capacity=_int(raw, "capacity", "seatCount"),
        )
