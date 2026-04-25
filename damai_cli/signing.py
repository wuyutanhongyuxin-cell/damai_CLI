from __future__ import annotations

import hashlib
import json
import time

# 大麦 H5 appKey，社区逆向所得
APP_KEY_H5 = "12574478"
# 默认 JSV 版本，与 H5 端保持一致
DEFAULT_JSV = "2.7.2"


def sign_h5(token: str, t: int | str, app_key: str, data: str) -> str:
    # 拼接待签字符串，规则来自大麦 mtop H5 协议
    raw = f"{token}&{t}&{app_key}&{data}"
    return hashlib.md5(raw.encode()).hexdigest()


def build_mtop_params(
    api: str,
    version: str,
    data: dict | str,
    token: str,
    *,
    app_key: str = APP_KEY_H5,
    jsv: str = DEFAULT_JSV,
    t: int | None = None,
) -> dict:
    # t 未传时取当前毫秒时间戳
    if t is None:
        t = int(time.time() * 1000)

    # dict 转紧凑 JSON，禁止 ASCII 转义（含中文场景）
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        data_str = data

    sign = sign_h5(token, t, app_key, data_str)

    return {
        "jsv": jsv,
        "appKey": app_key,
        "t": str(t),
        "sign": sign,
        "api": api,
        "v": version,
        "type": "originaljson",
        "dataType": "json",
        "timeout": "20000",
        "data": data_str,
    }


def build_mtop_url(api: str, version: str, host: str = "mtop.damai.cn") -> str:
    # 标准 mtop H5 路径格式
    return f"https://{host}/h5/{api}/{version}/"
