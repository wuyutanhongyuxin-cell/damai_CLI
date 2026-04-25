from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ──────────────────────────────────────────────────────────────
# smoke marker 注册
# （pyproject.toml 里已声明，这里作为 hook 保底，避免 UnknownMarkWarning）
# ──────────────────────────────────────────────────────────────
def pytest_configure(config):
    """注册自定义 marker。"""
    config.addinivalue_line(
        "markers",
        "smoke: 需要真实网络和有效 Cookie，CI 默认跳过",
    )


# ──────────────────────────────────────────────────────────────
# Fixture：临时 Cookie 文件
# ──────────────────────────────────────────────────────────────
@pytest.fixture()
def tmp_cookie_path(tmp_path: Path) -> Path:
    """返回临时 cookies.json 路径，预填最小可登录 Cookie 集合。

    _m_h5_tk 格式：32位MD5_时间戳毫秒，token 取下划线前段。
    saved_at=0 使文件看起来刚刚保存（mtime 由 CookieJar.save 维护）。
    """
    cookie_data = {
        "saved_at": 0,
        "cookies": {
            "_m_h5_tk": "abcdef1234567890abcdef1234567890_1234567890000",
            "_m_h5_tk_enc": "mock_enc_value",
            "cna": "mock_cna",
            "cookie2": "mock_cookie2",
            "_tb_token_": "mock_tb_token",
            "isg": "mock_isg",
            "login": "true",
            "_nk_": "mock_nickname",
        },
    }
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps(cookie_data, ensure_ascii=False), encoding="utf-8")
    return path


# ──────────────────────────────────────────────────────────────
# Fixture：Mock MtopClient
# ──────────────────────────────────────────────────────────────
@pytest.fixture()
def mock_mtop_client():
    """返回一个 MagicMock，模拟 MtopClient 的 request 接口。

    用法：
        mock_mtop_client.request.return_value = {"result": [...]}
    支持 context manager：with get_client() as c
    """
    client = MagicMock()
    # 默认返回空 dict，各测试按需覆盖
    client.request.return_value = {}
    # 支持 with 语句
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client
