from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from damai_cli.cookies import CookieJar


# ─────────────────────────────────────────
# 辅助：构造带初始数据的 CookieJar
# ─────────────────────────────────────────

def _make_jar(tmp_path: Path, initial: dict | None = None) -> CookieJar:
    """在临时目录创建 CookieJar，可选写入初始 Cookie。"""
    jar = CookieJar(path=tmp_path / "cookies.json")
    if initial:
        jar.save(initial)
    return jar


# ─────────────────────────────────────────
# 测试函数
# ─────────────────────────────────────────

def test_save_creates_file(tmp_path: Path) -> None:
    """save 后文件应当存在，且内容为合法 JSON。"""
    jar = _make_jar(tmp_path)
    jar.save({"cna": "abc123", "login": "true"})
    assert jar.path.exists()
    with jar.path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["cna"] == "abc123"
    assert data["login"] == "true"


def test_load_returns_saved_data(tmp_path: Path) -> None:
    """load 应读回 save 写入的内容。"""
    jar = _make_jar(tmp_path, {"_nk_": "testuser", "cookie2": "c2value"})
    # 新建一个 jar 指向同一路径，确认从文件读
    jar2 = CookieJar(path=tmp_path / "cookies.json")
    result = jar2.load()
    assert result["_nk_"] == "testuser"
    assert result["cookie2"] == "c2value"


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    """文件不存在时 load 应返回空字典，不抛异常。"""
    jar = CookieJar(path=tmp_path / "no_such.json")
    result = jar.load()
    assert result == {}


def test_update_merges_and_persists(tmp_path: Path) -> None:
    """update 应合并新旧键，并写回文件。"""
    jar = _make_jar(tmp_path, {"cna": "old_cna"})
    jar.load()
    jar.update({"login": "true", "cna": "new_cna"})
    # 内存中应合并
    assert jar.get("login") == "true"
    assert jar.get("cna") == "new_cna"
    # 文件也应持久化
    with jar.path.open("r", encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk["login"] == "true"
    assert on_disk["cna"] == "new_cna"


def test_clear_removes_file(tmp_path: Path) -> None:
    """clear 应清空内存并删除文件。"""
    jar = _make_jar(tmp_path, {"login": "true"})
    jar.load()
    jar.clear()
    assert not jar.path.exists()
    # 内存也应为空
    assert jar.get("login") is None


def test_get_token_splits_correctly(tmp_path: Path) -> None:
    """get_token 应从 _m_h5_tk 取下划线前的 MD5 部分。"""
    jar = _make_jar(tmp_path, {"_m_h5_tk": "abc_xyz"})
    jar.load()
    assert jar.get_token() == "abc"


def test_get_token_real_format(tmp_path: Path) -> None:
    """典型真实格式：32 位 MD5 + _ + 13 位时间戳。"""
    md5_part = "a" * 32
    ts_part = "1234567890123"
    jar = _make_jar(tmp_path, {"_m_h5_tk": f"{md5_part}_{ts_part}"})
    jar.load()
    assert jar.get_token() == md5_part


def test_get_token_missing_returns_none(tmp_path: Path) -> None:
    """_m_h5_tk 不存在时 get_token 应返回 None。"""
    jar = _make_jar(tmp_path, {"cna": "only_cna"})
    jar.load()
    assert jar.get_token() is None


def test_as_header_format(tmp_path: Path) -> None:
    """as_header 输出格式应为 'k1=v1; k2=v2'，包含所有键。"""
    data = {"a": "1", "b": "2"}
    jar = _make_jar(tmp_path, data)
    jar.load()
    header = jar.as_header()
    # 顺序由字典插入顺序决定，只校验内容包含性
    assert "a=1" in header
    assert "b=2" in header
    # 分隔符应为 "; "
    parts = header.split("; ")
    assert len(parts) == 2


def test_is_expired_fresh_file(tmp_path: Path) -> None:
    """刚写入的文件 mtime 在 7 天内，is_expired 应为 False。"""
    jar = _make_jar(tmp_path, {"login": "true"})
    assert not jar.is_expired()


def test_is_expired_old_file(tmp_path: Path) -> None:
    """用 os.utime 将 mtime 设为 8 天前，is_expired 应为 True。"""
    jar = _make_jar(tmp_path, {"login": "true"})
    # 设置 mtime 为 8 天前
    old_time = time.time() - 8 * 86400
    os.utime(jar.path, (old_time, old_time))
    assert jar.is_expired()


def test_is_expired_missing_file(tmp_path: Path) -> None:
    """文件不存在时 is_expired 应返回 True。"""
    jar = CookieJar(path=tmp_path / "nonexistent.json")
    assert jar.is_expired()


def test_is_logged_in_via_login_flag(tmp_path: Path) -> None:
    """login=true 时 is_logged_in 应为 True。"""
    jar = _make_jar(tmp_path, {"login": "true"})
    jar.load()
    assert jar.is_logged_in()


def test_is_logged_in_via_nk(tmp_path: Path) -> None:
    """_nk_ 存在时（无 login 键）也应视为已登录。"""
    jar = _make_jar(tmp_path, {"_nk_": "someone"})
    jar.load()
    assert jar.is_logged_in()


def test_is_logged_in_via_cookie2(tmp_path: Path) -> None:
    """cookie2 存在时应视为已登录。"""
    jar = _make_jar(tmp_path, {"cookie2": "c2val"})
    jar.load()
    assert jar.is_logged_in()


def test_is_logged_in_empty(tmp_path: Path) -> None:
    """没有任何登录标志时 is_logged_in 应为 False。"""
    jar = _make_jar(tmp_path, {"cna": "only_cna"})
    jar.load()
    assert not jar.is_logged_in()


def test_no_setitem_exposed(tmp_path: Path) -> None:
    """CookieJar 不应暴露 __setitem__，防止绕过持久化。"""
    jar = _make_jar(tmp_path)
    assert not hasattr(jar, "__setitem__")
