from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from damai_cli.client import MtopClient
from damai_cli.commands.reading import _flatten_detail
from damai_cli.cookies import CookieJar
from damai_cli.models import Artist, Order, Show, Viewer

CAPTURE_DIR = Path(__file__).parent.parent / "tmp_captures"


def _load_body(api: str) -> dict:
    # 'mtop.damai.foo.bar' → 'mtop_damai_foo_bar.json'，取 response_body 字段
    fn = "mtop_" + api.replace("mtop.", "", 1).replace(".", "_") + ".json"
    raw = json.loads((CAPTURE_DIR / fn).read_text(encoding="utf-8"))
    return raw["response_body"]


@pytest.fixture
def patch_jitter(monkeypatch):
    # _jitter_sleep 默认会 sleep 1 秒+，离线测试堆叠会拖很慢
    monkeypatch.setattr("damai_cli.client._jitter_sleep", lambda *a, **k: None)


@pytest.fixture
def isolated_jar(tmp_path):
    # 防止 _do_request 里的 jar.save 写到用户全局 ~/.damai-cli/cookies.json
    jar = CookieJar(path=tmp_path / "cookies.json")
    jar.save({"_m_h5_tk": "deadbeef00000000deadbeef00000000_1700000000000"})
    return jar


def _make_client(api_to_body: dict, jar: CookieJar) -> MtopClient:
    def handler(request: httpx.Request) -> httpx.Response:
        api = request.url.params.get("api", "")
        body = api_to_body.get(api) or {"ret": ["SUCCESS::ok"], "data": {}}
        return httpx.Response(200, json=body)
    client = MtopClient(cookies=jar)
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))
    return client


class TestReadingParse:
    def test_search(self, patch_jitter, isolated_jar):
        api = "mtop.damai.wireless.search.search"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "1.0", {"keyword": "test"})
        items = data.get("projectInfo") or []
        assert items
        show = Show.from_dict(items[0])
        assert show.id and show.name

    def test_show_detail_with_flatten(self, patch_jitter, isolated_jar):
        # 同时覆盖 reading._flatten_detail（嵌套 item/venue/price/guide → flat）
        api = "mtop.damai.item.detail.getdetail"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "1.0", {"itemId": "123"})
        flat = _flatten_detail(data)
        show = Show.from_dict(flat)
        assert show.id and show.name

    def test_hot(self, patch_jitter, isolated_jar):
        api = "mtop.damai.wireless.search.broadcast.home"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "1.0", {"cityId": "852"})
        projects = data.get("projects") or []
        assert projects
        shows = [Show.from_dict(x) for x in projects]
        assert all(s.id for s in shows)

    def test_calendar(self, patch_jitter, isolated_jar):
        api = "mtop.damai.wireless.search.project.classify"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "1.0", {"currentCityId": "852"})
        items = data.get("nearByCity") or []
        assert items
        shows = [Show.from_dict(x) for x in items]
        assert any(s.name for s in shows)

    def test_artist(self, patch_jitter, isolated_jar):
        # CONTRACTS 标注 pending：by-name 接口未抓到，真实 capture data 是
        # {all, more} 嵌套结构，此测试仅验解析链路不崩
        api = "mtop.damai.wireless.channel.artiste"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "1.0", {"artistName": "x"})
        Artist.from_dict(data)

    def test_category(self, patch_jitter, isolated_jar):
        api = "mtop.damai.wireless.search.cms.category.get"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "2.0", {"apiVersion": "3.1"})
        cats = data.get("data")
        assert isinstance(cats, list)


class TestAccountParse:
    def test_orders(self, patch_jitter, isolated_jar):
        # 空账户 capture：data 是 {}，orderList 缺失。验解析链路不崩
        api = "mtop.damai.wireless.order.orderlist"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "2.0", {"queryType": "0"})
        for o in data.get("orderList") or []:
            Order.from_dict(o)

    def test_viewers(self, patch_jitter, isolated_jar):
        # 空账户 capture：data 是 {}，customerList 缺失。验解析链路不崩
        api = "mtop.damai.wireless.user.customerlist.get"
        with _make_client({api: _load_body(api)}, isolated_jar) as c:
            data = c.request(api, "2.0", {"customerType": "default"})
        for v in data.get("customerList") or []:
            Viewer.from_dict(v)


def test_entry_point_executable():
    # 调用 pip install 生成的 damai entry script（不是 `python -m damai_cli.cli`，
    # 后者因 cli.py:_try_register 用 __name__.rsplit 推断 package 在 -m 模式下失效）
    suffix = ".exe" if sys.platform == "win32" else ""
    damai_exe = Path(sys.executable).parent / f"damai{suffix}"
    assert damai_exe.exists(), f"entry script {damai_exe} 不存在；pip install -e . 未跑？"
    result = subprocess.run([str(damai_exe), "--help"], capture_output=True, timeout=15)
    assert result.returncode == 0
    out = result.stdout.decode("utf-8", errors="replace")
    for name in ("search", "show", "hot", "calendar", "build", "submit", "login"):
        assert name in out, f"子命令 {name} 未在 --help 输出中"
