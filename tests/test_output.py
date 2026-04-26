from __future__ import annotations

import json
import sys

# --- 测试 ok() ---

def test_ok_has_required_fields():
    from damai_cli.output import SCHEMA_VERSION, ok
    result = ok({"foo": "bar"})
    assert result["ok"] is True
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["data"] == {"foo": "bar"}


def test_ok_with_pagination():
    from damai_cli.output import ok
    result = ok([], pagination={"page": 1, "total": 100})
    assert "pagination" in result
    assert result["pagination"]["total"] == 100


def test_ok_without_pagination_no_key():
    from damai_cli.output import ok
    result = ok([])
    assert "pagination" not in result


# --- 测试 err() ---

def test_err_has_error_code():
    from damai_cli.output import SCHEMA_VERSION, err
    result = err("not_found", "资源不存在")
    assert result["ok"] is False
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["error"]["code"] == "not_found"
    assert result["error"]["message"] == "资源不存在"


def test_err_extra_included():
    from damai_cli.output import err
    result = err("invalid_input", "参数错误", field="keyword")
    assert result["error"]["extra"] == {"field": "keyword"}


def test_err_no_extra_when_empty():
    from damai_cli.output import err
    result = err("sign_failed", "签名失败")
    assert "extra" not in result["error"]


# --- 测试 detect_mode() ---

def test_detect_mode_env_rich(monkeypatch):
    from damai_cli import output
    monkeypatch.setenv("OUTPUT", "rich")
    assert output.detect_mode() == "rich"


def test_detect_mode_env_json(monkeypatch):
    from damai_cli import output
    monkeypatch.setenv("OUTPUT", "json")
    assert output.detect_mode() == "json"


def test_detect_mode_env_yaml(monkeypatch):
    from damai_cli import output
    monkeypatch.setenv("OUTPUT", "yaml")
    assert output.detect_mode() == "yaml"


def test_detect_mode_env_overrides_tty(monkeypatch):
    # 即使 stdout 是 tty，env 仍优先
    from damai_cli import output
    monkeypatch.setenv("OUTPUT", "json")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert output.detect_mode() == "json"


def test_detect_mode_no_env_tty(monkeypatch):
    from damai_cli import output
    monkeypatch.delenv("OUTPUT", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert output.detect_mode() == "rich"


def test_detect_mode_no_env_no_tty(monkeypatch):
    from damai_cli import output
    monkeypatch.delenv("OUTPUT", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert output.detect_mode() == "yaml"


# --- 测试异常类 .code 属性 ---

def test_exception_codes():
    from damai_cli.exceptions import (
        InvalidInput,
        IpBlocked,
        ItemNotStarted,
        ItemSoldOut,
        NeedSlideCaptcha,
        NetworkError,
        NotAuthenticated,
        NotFound,
        RateLimited,
        RealNameRequired,
        SessionExpired,
        SignFailed,
        TokenEmpty,
        Unsupported,
        UpstreamError,
    )
    cases = [
        (NotAuthenticated, "not_authenticated"),
        (SessionExpired, "session_expired"),
        (SignFailed, "sign_failed"),
        (NeedSlideCaptcha, "need_slide_captcha"),
        (IpBlocked, "ip_blocked"),
        (RateLimited, "rate_limited"),
        (ItemSoldOut, "item_sold_out"),
        (ItemNotStarted, "item_not_started"),
        (RealNameRequired, "real_name_required"),
        (NetworkError, "network_error"),
        (UpstreamError, "upstream_error"),
        (NotFound, "not_found"),
        (InvalidInput, "invalid_input"),
        (Unsupported, "unsupported"),
        (TokenEmpty, "token_empty"),
    ]
    for cls, expected_code in cases:
        assert cls.code == expected_code, f"{cls.__name__}.code should be {expected_code!r}"


def test_exception_message_str():
    from damai_cli.exceptions import DamaiError
    e = DamaiError("hello")
    assert str(e) == "hello"


def test_exception_extra():
    from damai_cli.exceptions import NetworkError
    e = NetworkError("连接超时", url="https://example.com")
    assert e.extra == {"url": "https://example.com"}


# --- 测试 emit() yaml/json 输出 ---

def test_emit_yaml_output(monkeypatch, capsys):
    from damai_cli.output import emit, ok
    monkeypatch.setenv("OUTPUT", "yaml")
    emit(ok({"key": "val"}))
    captured = capsys.readouterr()
    assert "ok: true" in captured.out


def test_emit_json_output(monkeypatch, capsys):
    from damai_cli.output import emit, ok
    monkeypatch.setenv("OUTPUT", "json")
    emit(ok({"key": "val"}))
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["ok"] is True
    assert parsed["data"]["key"] == "val"
