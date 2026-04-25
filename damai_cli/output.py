from __future__ import annotations

import json
import os
import sys

import yaml

# 输出 envelope 的 schema 版本，便于消费方做版本校验
SCHEMA_VERSION = "1"


def ok(data, pagination: dict | None = None) -> dict:
    # 构造成功 envelope
    envelope: dict = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "data": data,
    }
    if pagination is not None:
        envelope["pagination"] = pagination
    return envelope


def err(code: str, message: str, **extra) -> dict:
    # 构造失败 envelope
    error: dict = {"code": code, "message": message}
    if extra:
        error["extra"] = extra
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "error": error,
    }


def detect_mode() -> str:
    # env OUTPUT 优先；TTY → rich；非 TTY → yaml
    raw = os.environ.get("OUTPUT", "").strip().lower()
    if raw in ("rich", "yaml", "json"):
        return raw
    if sys.stdout.isatty():
        return "rich"
    return "yaml"


def _write_safe(text: str) -> None:
    """stdout.write 的 GBK-safe 包装，遇到不支持字符用 ? 替换而非崩溃。"""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        buf = getattr(sys.stdout, "buffer", None)
        payload = text.encode(enc, errors="replace")
        if buf is not None:
            buf.write(payload)
        else:
            sys.stdout.write(payload.decode(enc, errors="replace"))


def _emit_yaml(envelope: dict) -> None:
    _write_safe(yaml.safe_dump(envelope, allow_unicode=True, sort_keys=False))


def _emit_json(envelope: dict) -> None:
    _write_safe(json.dumps(envelope, ensure_ascii=False, indent=2))
    _write_safe("\n")


def emit(envelope: dict, mode: str | None = None) -> None:
    # mode=None 时自动探测；rich 走 formatter；其余走 stdout 序列化
    if mode is None:
        mode = detect_mode()

    if mode == "rich":
        from . import formatter  # 延迟导入，避免 rich 未安装时崩溃
        formatter.render_envelope_rich(envelope)
    elif mode == "json":
        _emit_json(envelope)
    else:
        # 默认 yaml（含未知 mode 兜底）
        _emit_yaml(envelope)
