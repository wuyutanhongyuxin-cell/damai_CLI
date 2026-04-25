from __future__ import annotations

import hashlib
import json

from damai_cli.signing import (
    APP_KEY_H5,
    DEFAULT_JSV,
    build_mtop_params,
    build_mtop_url,
    sign_h5,
)

# ---------------------------------------------------------------------------
# Golden vector：计算一次后锁定，防止函数被悄悄改动
# ---------------------------------------------------------------------------

_GOLDEN_TOKEN = "abc123"
_GOLDEN_T = 1700000000000
_GOLDEN_APP_KEY = "12574478"
_GOLDEN_DATA = '{"k":"v"}'

# 在模块加载时用标准库独立计算，作为预期值
_GOLDEN_SIGN: str = hashlib.md5(
    f"{_GOLDEN_TOKEN}&{_GOLDEN_T}&{_GOLDEN_APP_KEY}&{_GOLDEN_DATA}".encode()
).hexdigest()


# ---------------------------------------------------------------------------
# sign_h5 测试
# ---------------------------------------------------------------------------


def test_sign_h5_golden_vector() -> None:
    """sign_h5 对已知向量的返回值须与独立计算结果完全一致。"""
    result = sign_h5(_GOLDEN_TOKEN, _GOLDEN_T, _GOLDEN_APP_KEY, _GOLDEN_DATA)
    assert result == _GOLDEN_SIGN


def test_sign_h5_returns_32_hex_chars() -> None:
    """MD5 摘要固定 32 个十六进制字符。"""
    result = sign_h5("tok", 0, "key", "data")
    assert len(result) == 32
    assert all(c in "0123456789abcdef" for c in result)


def test_sign_h5_different_inputs_differ() -> None:
    """不同输入必须产生不同签名（碰撞概率极低）。"""
    s1 = sign_h5("tok1", 1000, APP_KEY_H5, "{}")
    s2 = sign_h5("tok2", 1000, APP_KEY_H5, "{}")
    assert s1 != s2


# ---------------------------------------------------------------------------
# build_mtop_params 测试
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {"jsv", "appKey", "t", "sign", "api", "v", "type", "dataType", "timeout", "data"}


def test_build_mtop_params_required_keys() -> None:
    """返回字典须包含契约规定的全部 key。"""
    params = build_mtop_params("some.api", "1.0", {"x": 1}, "mytoken", t=_GOLDEN_T)
    assert _REQUIRED_KEYS.issubset(params.keys())


def test_build_mtop_params_data_is_compact_json() -> None:
    """dict 入参须序列化为无空格紧凑 JSON。"""
    params = build_mtop_params("api", "1.0", {"a": 1, "b": 2}, "tok", t=1)
    # 紧凑格式：无空格、冒号/逗号直连
    assert " " not in params["data"]
    # 可反序列化回原始内容
    assert json.loads(params["data"]) == {"a": 1, "b": 2}


def test_build_mtop_params_sign_consistent_with_sign_h5() -> None:
    """params['sign'] 须等于用相同参数调 sign_h5 的结果。"""
    params = build_mtop_params(
        _GOLDEN_TOKEN,
        "1.0",
        _GOLDEN_DATA,
        _GOLDEN_TOKEN,
        app_key=_GOLDEN_APP_KEY,
        t=_GOLDEN_T,
    )
    expected = sign_h5(_GOLDEN_TOKEN, _GOLDEN_T, _GOLDEN_APP_KEY, params["data"])
    assert params["sign"] == expected


def test_build_mtop_params_t_is_string() -> None:
    """t 字段须为字符串类型（mtop 协议要求）。"""
    params = build_mtop_params("api", "1.0", {}, "tok", t=1700000000000)
    assert isinstance(params["t"], str)
    assert params["t"] == "1700000000000"


def test_build_mtop_params_defaults() -> None:
    """默认 jsv / appKey 须与常量一致；t 不传时须为合理毫秒时间戳。"""
    import time

    before = int(time.time() * 1000)
    params = build_mtop_params("api", "1.0", {}, "tok")
    after = int(time.time() * 1000)

    assert params["jsv"] == DEFAULT_JSV
    assert params["appKey"] == APP_KEY_H5
    assert before <= int(params["t"]) <= after


def test_build_mtop_params_string_data_passthrough() -> None:
    """data 已是字符串时，不应再次序列化（直接透传）。"""
    raw = '{"already":"json"}'
    params = build_mtop_params("api", "1.0", raw, "tok", t=1)
    assert params["data"] == raw


# ---------------------------------------------------------------------------
# build_mtop_url 测试
# ---------------------------------------------------------------------------


def test_build_mtop_url_default_host() -> None:
    """默认 host 拼出标准大麦 mtop 路径。"""
    url = build_mtop_url("mtop.damai.search.searchresult", "1.0")
    assert url == "https://mtop.damai.cn/h5/mtop.damai.search.searchresult/1.0/"


def test_build_mtop_url_custom_host() -> None:
    """host 可被覆盖（用于测试/代理场景）。"""
    url = build_mtop_url("some.api", "2.0", host="mock.example.com")
    assert url == "https://mock.example.com/h5/some.api/2.0/"


def test_build_mtop_url_ends_with_slash() -> None:
    """路径末尾必须有 /（大麦服务端严格匹配）。"""
    url = build_mtop_url("a.b.c", "1.2")
    assert url.endswith("/")
