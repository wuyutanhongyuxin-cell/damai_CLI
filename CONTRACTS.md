# damai-cli 模块契约（所有 subagent 共享）

> Last synced against real MTOP capture: 2026-04-24 (tmp_captures/*.json, 17 APIs)

## 硬约束
- Python 3.10+
- 单源码文件 ≤ 200 行，单函数 ≤ 30 行，测试 ≤ 300 行
- 中文注释，只在 why 不明显处写，不要长 docstring
- **不要联网**：不 WebFetch / WebSearch，按本契约实现
- **契约不可变**：若发现契约不合理，只在汇报里指出，不要擅自改
- 使用 `from __future__ import annotations` 统一
- 不写 emoji

> **MTOP 公共参数强制注入**：所有大麦 H5 MTOP 请求的业务 `data` dict 必须包含 `platform=8, comboChannel=2, dmChannel=damai@damaih5_h5`，缺失会被接口拒。由 `MtopClient._do_request` 统一注入，调用方不需手动传。

## 项目根
`E:\claude_ask\sjtu_CLI\damai-cli\`

## 完整文件树
```
damai-cli/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── SKILL.md
├── SCHEMA.md
├── CONTRACTS.md                 # 本文件
├── .gitignore
├── tasks/todo.md                # 已存在
├── damai_cli/
│   ├── __init__.py
│   ├── cli.py
│   ├── client.py
│   ├── signing.py
│   ├── cookies.py
│   ├── auth.py
│   ├── qr_login.py
│   ├── password_login.py
│   ├── browser_cookie.py
│   ├── exceptions.py
│   ├── formatter.py
│   ├── output.py
│   ├── config.py
│   ├── filter.py
│   ├── models.py
│   └── commands/
│       ├── __init__.py
│       ├── _common.py
│       ├── auth.py
│       ├── reading.py
│       ├── account.py
│       ├── track.py
│       └── trade.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_signing.py
    ├── test_cookies.py
    └── test_output.py
```

## 错误码清单（15 个）
`not_authenticated` / `session_expired` / `sign_failed` / `need_slide_captcha` / `ip_blocked` / `rate_limited` / `item_sold_out` / `item_not_started` / `real_name_required` / `network_error` / `upstream_error` / `not_found` / `invalid_input` / `unsupported` / `token_empty`

## 模块契约

### exceptions.py
```python
class DamaiError(Exception):
    code: str = "upstream_error"
    def __init__(self, message: str = "", **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra

class NotAuthenticated(DamaiError):      code = "not_authenticated"
class SessionExpired(DamaiError):        code = "session_expired"
class SignFailed(DamaiError):            code = "sign_failed"
class NeedSlideCaptcha(DamaiError):      code = "need_slide_captcha"
class IpBlocked(DamaiError):             code = "ip_blocked"
class RateLimited(DamaiError):           code = "rate_limited"
class ItemSoldOut(DamaiError):           code = "item_sold_out"
class ItemNotStarted(DamaiError):        code = "item_not_started"
class RealNameRequired(DamaiError):      code = "real_name_required"
class NetworkError(DamaiError):          code = "network_error"
class UpstreamError(DamaiError):         code = "upstream_error"
class NotFound(DamaiError):              code = "not_found"
class InvalidInput(DamaiError):          code = "invalid_input"
class Unsupported(DamaiError):           code = "unsupported"
class TokenEmpty(DamaiError):            code = "token_empty"
```

### output.py
```python
SCHEMA_VERSION = "1"

def ok(data, pagination: dict | None = None) -> dict: ...
def err(code: str, message: str, **extra) -> dict: ...
def detect_mode() -> str:  # 返回 rich/yaml/json；env OUTPUT 优先，否则 TTY→rich/非TTY→yaml
    ...
def emit(envelope: dict, mode: str | None = None) -> None:
    # mode=None 时调 detect_mode()；rich 走 formatter.render_*；yaml/json 走 stdout
    ...
```

### formatter.py
```python
def render_table(rows: list[dict], columns: list[str], title: str = "") -> None: ...
def render_detail(obj: dict, title: str = "") -> None: ...  # Rich Panel
def render_list(items: list[str]) -> None: ...
def render_envelope_rich(envelope: dict) -> None:
    # 由 output.emit(rich) 调用；根据 data 类型自动选渲染方式
    ...
```

### config.py
```python
from pathlib import Path

CONFIG_DIR: Path        # Path.home() / ".damai-cli"
CONFIG_FILE: Path       # CONFIG_DIR / "config.yaml"
COOKIES_FILE: Path      # CONFIG_DIR / "cookies.json"
CACHE_DIR: Path         # CONFIG_DIR / "cache"
QR_FILE: Path           # CONFIG_DIR / "qr.png"

DEFAULT_CONFIG: dict    # 默认配置

def ensure_dirs() -> None: ...
def load_config() -> dict: ...
def save_config(cfg: dict) -> None: ...
def get_env(key: str, default: str | None = None) -> str | None:
    # 读 DAMAI_<KEY>
    ...
```

### cookies.py
```python
class CookieJar:
    TTL_SECONDS = 7 * 86400
    def __init__(self, path: Path | None = None): ...
    @property
    def path(self) -> Path: ...
    def load(self) -> dict[str, str]: ...
    def save(self, cookies: dict[str, str]) -> None: ...
    def update(self, cookies: dict[str, str]) -> None: ...
    def clear(self) -> None: ...
    def get(self, key: str) -> str | None: ...
    def get_token(self) -> str | None:
        # _m_h5_tk 值按 "_" 分割取前段（32 位 MD5）
        ...
    def as_header(self) -> str:
        # "k1=v1; k2=v2" 格式
        ...
    def is_expired(self) -> bool:
        # 根据文件 mtime + TTL
        ...
    def is_logged_in(self) -> bool:
        # 简单判断：login=true 或存在 _nk_/cookie2
        ...
```

### signing.py
```python
APP_KEY_H5 = "12574478"            # 大麦 H5 appKey（社区逆向值）
DEFAULT_JSV = "2.7.2"

def sign_h5(token: str, t: int | str, app_key: str, data: str) -> str:
    # md5(f"{token}&{t}&{app_key}&{data}").hexdigest()
    ...

def build_mtop_params(
    api: str,
    version: str,
    data: dict,
    token: str,
    *,
    app_key: str = APP_KEY_H5,
    jsv: str = DEFAULT_JSV,
    t: int | None = None,
) -> dict:
    # 返回 {jsv, appKey, t, sign, api, v, type, dataType, data}
    # data 参数若为 dict 先 json.dumps(ensure_ascii=False, separators=(',', ':'))
    ...

def build_mtop_url(api: str, version: str, host: str = "mtop.damai.cn") -> str:
    # f"https://{host}/h5/{api}/{version}/"
    ...
```

### client.py
```python
class MtopClient:
    def __init__(
        self,
        cookies: CookieJar | None = None,
        *,
        timeout: float = 15.0,
        user_agent: str | None = None,
        host: str = "mtop.damai.cn",
    ): ...

    def request(
        self,
        api: str,
        version: str = "1.0",
        data: dict | None = None,
        *,
        need_login: bool = False,
        method: str = "GET",
    ) -> dict:
        """发送 MTOP 请求；返回 upstream 响应里的 data 字段。
        异常映射：
          - FAIL_SYS_TOKEN_EMPTY / EXPIRED → 从 Set-Cookie 取新 _m_h5_tk 重签重试 1 次；仍失败 raise TokenEmpty
          - FAIL_SYS_SESSION_EXPIRED → SessionExpired
          - RGV587_ERROR / 滑块 → NeedSlideCaptcha
          - SM_CODE::1999 类风控 → IpBlocked
          - sold_out → ItemSoldOut
          - HTTP 429 / SM_CODE::FAIL_SYS_USER_FLOW_LIMIT → RateLimited，外层重试指数退避 5/10/20/30s
          - 其他 FAIL_SYS_* → UpstreamError
          - httpx.* 网络错误 → NetworkError
        """

    def close(self) -> None: ...
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
```

### models.py
```python
from dataclasses import dataclass, asdict

@dataclass(slots=True)
class Show:
    id: str
    name: str
    city: str | None = None
    venue: str | None = None
    category: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    status: str | None = None          # on_sale / pre_sale / ended
    start_time: str | None = None       # ISO 8601
    poster_url: str | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Show": ...

@dataclass(slots=True)
class Perform:
    perform_id: str; show_id: str; start_time: str | None = None; venue: str | None = None; seat_map_url: str | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Perform": ...

@dataclass(slots=True)
class Sku:
    sku_id: str; perform_id: str; price: float; description: str | None = None; stock_status: str | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Sku": ...

@dataclass(slots=True)
class Viewer:
    viewer_id: str; name: str; cert_type: str | None = None; cert_no_masked: str | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Viewer": ...

@dataclass(slots=True)
class Order:
    order_id: str; show_name: str; perform_time: str | None = None; status: str | None = None; total_fee: float | None = None; pay_url: str | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Order": ...

@dataclass(slots=True)
class Artist:
    id: str; name: str; follower_count: int | None = None; upcoming_count: int | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Artist": ...

@dataclass(slots=True)
class Venue:
    id: str; name: str; city: str | None = None; address: str | None = None; capacity: int | None = None
    @classmethod
    def from_dict(cls, raw: dict) -> "Venue": ...
```

### filter.py
```python
def rank_shows(shows: list[Show], *, w_hotness=0.3, w_time=0.2, w_price=0.1) -> list[Show]: ...
def filter_by_city(shows: list[Show], city: str) -> list[Show]: ...
def filter_by_status(shows: list[Show], status: str) -> list[Show]: ...
def filter_by_category(shows: list[Show], category: str) -> list[Show]: ...
def filter_by_price(shows: list[Show], *, min_price: float | None = None, max_price: float | None = None) -> list[Show]: ...
```

### auth.py
```python
class AuthManager:
    def __init__(self, cookies: CookieJar, client: MtopClient): ...
    def current_status(self) -> dict:
        # 本地 Cookie 解析：cookie2 / _nk_ 任一存在即视为登录；
        # user_id ← unb，nickname ← urldecode(_nk_ 或 tracknick)，expires_at ← 文件 mtime + TTL。
        # 不调用 MTOP 接口（damai 没有公开的 getuserinfo，试过 FAIL_SYS_API_NOT_FOUNDED）。
        # 实测 `mtop.user.getusersimple` 1.0 也可用，但保留本地判定作为兜底以减少风控触发。
        # 返回 {"logged_in": bool, "user_id": str?, "nickname": str?, "expires_at": iso?}
        ...
    def login(self, method: str = "auto") -> dict:
        # method ∈ {auto, saved, browser, qr, password}
        # auto: saved → browser → qr（password 不走 auto，要显式 --method）
        # password 需要 self._prompt_credentials() 交互
        ...
    def logout(self) -> None: ...
```

### browser_cookie.py
```python
def extract_cookies(browsers: list[str] | None = None) -> dict[str, str]:
    """browser-cookie3 抓 .damai.cn 和 .taobao.com 域。
    browsers 默认 ['chrome','edge','firefox','brave']。
    无 Cookie → NotAuthenticated。
    """
```

### qr_login.py
```python
def qr_login(timeout: int = 180) -> dict[str, str]:
    """camoufox 打开 https://passport.damai.cn/login 并等 QR <img>。
    1. 抓 QR 图 URL → 下载 PNG 存 config.QR_FILE → qrcode-terminal 打印 ASCII
    2. 轮询 DOM 直到 login 态（或 url redirect 离开 passport）
    3. context.cookies() 导出全部，合并回 dict
    失败/超时 → NotAuthenticated
    """
```

### password_login.py
```python
def password_login(username: str, password: str) -> dict[str, str]:
    """httpx POST https://passport.damai.cn/newlogin/login.do
    遇到滑块响应（code=RGV587_ERROR / 包含 x5sec）→ NeedSlideCaptcha
    成功返回 Cookie dict
    """
```

### commands/_common.py
```python
import functools, sys, click
from ..output import ok, err, emit
from ..exceptions import DamaiError, NotAuthenticated

def run_command(handler):
    """装饰器：统一包 try/except + emit，非零码退出"""
    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            result = handler(*args, **kwargs)
            if isinstance(result, dict) and result.get("ok") in (True, False):
                emit(result)
            else:
                emit(ok(result))
        except NotAuthenticated as e:
            emit(err(e.code, str(e) or "请先 damai login"))
            sys.exit(2)
        except DamaiError as e:
            emit(err(e.code, str(e), **e.extra))
            sys.exit(1)
    return wrapper

def get_client(need_login: bool = False):
    """构造 MtopClient + CookieJar；need_login=True 时先校验"""
    ...
```

### commands/*.py 模板
```python
import click
from dataclasses import asdict
from ._common import run_command, get_client
from ..models import Show

# 响应字段路径因 API 而异：search→projectInfo / hot→projects / classify→nearByCity /
# detail→item+venue+price+guide 嵌套。必须对照 tmp_captures/*.json 真实 schema，
# 切勿复用 raw.get("result", []) —— 大麦接口没有叫 result 的通用包裹层。
def register(cli: click.Group) -> None:
    @cli.command(name="hot")
    @click.option("--city", default="852", show_default=True)
    @run_command
    def hot(city):
        with get_client() as c:
            raw = c.request("mtop.damai.wireless.search.broadcast.home", "1.0", {"cityId": city})
        shows = [Show.from_dict(x) for x in raw.get("projects") or []]
        return {"shows": [asdict(s) for s in shows]}
```

### cli.py
```python
import click
from . import __version__
from .commands import auth, reading, account, track, trade

@click.group(name="damai")
@click.version_option(__version__)
@click.option("--output", type=click.Choice(["rich", "yaml", "json"]), envvar="OUTPUT")
@click.pass_context
def cli(ctx, output):
    if output:
        import os; os.environ["OUTPUT"] = output

for m in (auth, reading, account, track, trade):
    m.register(cli)

if __name__ == "__main__":
    cli()
```

## 命令清单

### commands/auth.py
- `damai login [--method auto|browser|qr|password]`
- `damai logout`
- `damai status`
- `damai whoami`

### commands/reading.py
- `damai search [keyword] [--limit 20] [--city 852] [--category-id 0]` → mtop.damai.wireless.search.search 1.0；keyword 选填，非空时对 `projectInfo[].name` 做客户端 substring 过滤（真·服务端搜索接口未抓到）
- `damai show <item_id>` → mtop.damai.item.detail.getdetail 1.0；响应嵌套 `item/venue/price/guide/itemPics`，需扁平化后喂给 `Show.from_dict`；返回 `{show, buyButton}`（buyButton 原样，H5 部分演出会标禁购）
- `damai hot [--city 852]` → mtop.damai.wireless.search.broadcast.home 1.0；响应 `projects[]` + `top` 合并（top 置首）
- `damai calendar [--city 852] [--limit 15] [--category-id 0]` → mtop.damai.wireless.search.project.classify 1.0；响应 `nearByCity[]`
- `damai artist [name] --group-id <id>` → mtop.damai.wireless.channel.artiste 1.0；接口本质是"列出品类 groupId 下全部艺人"，响应 `data.more.list[]` 为 `{id,name,pinyin}`；name 非空时本地 substring 过滤。真·by-name 查询接口未抓到
- `damai venue <id>` → mtop.damai.mdata.venue.getvenuedetail  # pending capture：独立场馆 API 未抓到
- `damai category` → 动态（mtop.damai.wireless.search.cms.category.get 2.0，data={"apiVersion":"3.1"}，响应 `data[]`）+ 本地静态兜底表

### commands/account.py
- `damai favorites` → mtop.damai.user.myfavorite  # pending capture：列表 API 仍未捕获。已抓到的 mtop.damai.wireless.user.my.content.get 只返回"我的"页面计数（praiseWantCount/myFollowCount 等），不含演出列表；当前 API 名 myfavorite 是猜测值未经真实流量验证
- `damai orders [--status pending|paid|refunded]` → mtop.damai.wireless.order.orderlist 2.0；必填 payload `{queryType:"0", queryOrderType:1, pageNum:1, pageSize:10, bindUserIdList:"[]"}`；响应 `orderList[]`；`--status` 选项当前未映射到服务端（空账户无订单可验证状态字段）
- `damai viewers` → mtop.damai.wireless.user.customerlist.get 2.0；必填 payload `{customerType:"default"}`；响应 `customerList[]`（空账户返回空数组，真字段待真账户验证）

### commands/track.py
- `damai track <item_id> --perform <id> [--notify] [--interval 30]`
  轮询 detail.getdetail，status 变 on_sale 时通过 plyer.notification 弹通知

### commands/trade.py
- `damai build <item_id> --perform X --sku Y --viewer Z [--count 1]` → mtop.trade.order.build.h5 1.0；输出 build_token + 订单预览  # pending capture
- `damai submit <build_token> [--i-understand-risk]` → mtop.trade.order.create.h5 1.0；没有 flag 则 dry-run 打印 payload  # pending capture
- `damai buy <item_id> --perform X --sku Y --viewer Z [--auto-submit] [--i-understand-risk]`  # pending capture
- `damai pay-url <order_id>` → mtop.trade.order.pay.getpayurl  # pending capture

## 联合测试要点

- 所有 `test_*.py` 默认 `pytest -q` 可跑（不依赖网络）
- 真 API 用 `@pytest.mark.smoke` 标记并存在 `tests/smoke/` 下，CI 默认跳过
- `pyproject.toml` 里 `[tool.pytest.ini_options]` 加：
  ```toml
  markers = ["smoke: hit real API"]
  addopts = "-m 'not smoke'"
  ```

## 依赖（pyproject.toml [project].dependencies）

```
click>=8.1
httpx>=0.27
rich>=13.7
pyyaml>=6
browser-cookie3>=0.19
qrcode-terminal>=0.8
plyer>=2.1          # 系统通知
camoufox>=0.3       # QR 登录无头浏览器（可选：optional-dependencies.qr）
```

可选组：
```
[project.optional-dependencies]
qr = ["camoufox>=0.3"]
tls = ["curl_cffi>=0.7"]
dev = ["pytest>=7", "pytest-asyncio>=0.23", "ruff>=0.4", "mypy>=1.10"]
```

## 入口脚本

```
[project.scripts]
damai = "damai_cli.cli:cli"
```
