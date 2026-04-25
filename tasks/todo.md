# damai-cli 实现规划

> 参考：`E:\claude_ask\sjtu_CLI\CLI项目学习总结.md`
> 最贴近的参考项目：**xiaohongshu-cli**（签名体系 + 反爬 + camoufox QR 登录）、**twitter-cli**（GraphQL 逆向 + TLS 指纹）、**bilibili-cli**（三级认证 + QR + Envelope）
> 决策：Python 3.10+ · 全功能（阅览 + 建单 + 下单）· 四级登录

---

## 1. 功能范围

### 1.1 只读类（阅览，不依赖登录）
| 命令 | 功能 | 后端 API |
|------|------|---------|
| `damai search <keyword>` | 搜索演出 | `mtop.damai.search.searchresult` |
| `damai show <item_id>` | 演出详情（场次/价位/座位图） | `mtop.alibaba.damai.detail.getdetail` |
| `damai hot` | 热门榜 | `mtop.damai.mdata.topic.gethotlist` |
| `damai calendar [--city X] [--days 7]` | 日历 | `mtop.damai.mdata.tag.recommend` |
| `damai artist <name>` | 艺人演出列表 | `mtop.damai.mdata.artist.getartistdata` |
| `damai venue <id>` | 场馆信息 | `mtop.damai.mdata.venue.getvenuedetail` |
| `damai category` | 分类/城市枚举 | 静态 + `mtop.damai.mdata.region.getregionlist` |

### 1.2 账户类（登录后可用）
| 命令 | 功能 |
|------|------|
| `damai login [--method qr\|browser\|password]` | 登录 |
| `damai logout` | 清除凭证 |
| `damai status` / `damai whoami` | 查登录状态 |
| `damai favorites` | 关注/想看列表 |
| `damai orders [--status pending\|paid\|refunded]` | 订单列表 |
| `damai viewers` | 实名观演人列表 |

### 1.3 交易类（写操作，高风险）
| 命令 | 功能 | 后端 API |
|------|------|---------|
| `damai track <item_id> --notify` | 开票监控（本地定时轮询 + 系统通知） | 用 detail.getdetail 轮询 |
| `damai build <item_id> --perform <场次> --sku <价位> --viewer <观演人id>` | 建单（停在支付前） | `mtop.trade.order.build.h5` |
| `damai submit <build_token>` | 提交订单 | `mtop.trade.order.create.h5` |
| `damai buy <item_id> --perform X --sku Y --viewer Z [--auto-submit]` | 一键抢票（默认只建单，`--auto-submit` 才走 submit） | build + create 组合 |
| `damai pay-url <order_id>` | 输出支付 URL（二次确认兜底） | `mtop.trade.order.pay.getpayurl` |

**风险护栏**（必须内置）：
- 所有写操作默认 `--dry-run` 到 stderr 打印即将发送的 payload
- 真正 submit 需要 `--i-understand-risk` 二次确认 flag
- 内置冷却：connect→401/461/471 → 指数退避 5s→10s→20s→30s（仿 xhs-cli）
- 实名观演人必须从账户已绑定列表选，不支持新建（避免触发风控）

---

## 2. 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.10+ | 参考生态一致 |
| CLI | `click` ≥ 8 | 全员标配 |
| HTTP | `httpx` + `curl_cffi`（可选 TLS 指纹） | httpx 异步；curl_cffi 对付 Cloudflare-like 指纹校验 |
| 输出 | `rich` + `pyyaml` | 三级输出（rich/yaml/json）+ Envelope |
| 签名 | 自实现 `md5(_m_h5_tk前半段 + t + appKey + data)` | MTOP 协议公开，无需第三方 |
| 浏览器 Cookie | `browser-cookie3` | 4 个参考项目都用 |
| QR 登录 | `camoufox`（无头 Firefox）+ `qrcode-terminal` | 仿 xhs-cli，Firefox 指纹比 Chromium 风控宽 |
| 存储 | 无 DB，Cookie/缓存走 JSON | 读多写少，无消息流，不必 SQLite |
| 构建 | `hatchling` | 仿 xhs-cli |
| 测试 | `pytest` + `pytest-asyncio` + `pytest -m "not smoke"` 默认 | 仿 xhs-cli |

---

## 3. 目录结构

```
damai-cli/
├── pyproject.toml
├── README.md
├── SKILL.md              # 教 AI 如何用
├── SCHEMA.md             # Envelope 契约
├── CLAUDE.md             # 项目规范（沿用通用模板）
├── damai_cli/
│   ├── __init__.py
│   ├── cli.py            # Click 入口 + 子命令注册
│   ├── client.py         # HTTP + MTOP 签名 + 重试
│   ├── signing.py        # _m_h5_tk + sign 生成
│   ├── cookies.py        # Cookie 持久化 + TTL
│   ├── auth.py           # 三级认证调度
│   ├── qr_login.py       # camoufox QR 流程
│   ├── password_login.py # passport.damai.cn 表单（兜底，大概率失败）
│   ├── browser_cookie.py # browser-cookie3 封装
│   ├── exceptions.py     # 6 类异常
│   ├── formatter.py      # Rich + YAML/JSON
│   ├── output.py         # Envelope
│   ├── config.py         # 环境变量 + config.yaml
│   ├── filter.py         # 演出评分/过滤
│   ├── models.py         # Dataclass（Show/Perform/Sku/Order/Viewer）
│   └── commands/
│       ├── __init__.py
│       ├── auth.py       # login/logout/status/whoami
│       ├── reading.py    # search/show/hot/calendar/artist/venue/category
│       ├── account.py    # favorites/orders/viewers
│       ├── track.py      # 开票监控
│       └── trade.py      # build/submit/buy/pay-url
└── tests/
    ├── test_signing.py
    ├── test_client.py
    ├── test_cookies.py
    └── smoke/            # 真实 API，默认跳过
```

**文件行数约束**（仿通用模板）：单文件 ≤ 200 行，单目录 ≤ 2000 行，单函数 ≤ 30 行。

---

## 4. 输出 Envelope

```yaml
ok: true
schema_version: "1"
data: {...}
pagination:       # 可选
  nextCursor: "..."
```

错误码：`not_authenticated` / `session_expired` / `sign_failed` / `need_slide_captcha` / `ip_blocked` / `rate_limited` / `item_sold_out` / `item_not_started` / `real_name_required` / `network_error` / `upstream_error` / `not_found` / `invalid_input` / `unsupported`

---

## 5. 登录流程（核心难点）

```
damai login
  ├─ 0. 已保存 Cookie（~/.damai-cli/cookies.json）有效？→ 直接用
  ├─ 1. browser-cookie3 从 Chrome/Edge/Firefox 读 .damai.cn/.taobao.com 域 → 验证 mtop.damai.user.getuserinfo → 成功则回写 cookies.json
  ├─ 2. camoufox 打开 login.damai.cn → 终端打印 QR（ascii）+ 存文件 → 轮询 qrcodeLogin/qrcodeGenerateCode 状态 → 成功抓 Cookie → 回写
  └─ 3. (--method password) 表单 POST passport.damai.cn/newLogin/login.do → 遇到滑块直接失败返回 need_slide_captcha（不尝试绕过滑块）
```

**必需 Cookie**：`_m_h5_tk` + `_m_h5_tk_enc` + `cna` + `t` + `cookie2` + `_tb_token_` + `isg` + `login=true` + `_nk_`

**_m_h5_tk 自刷新**：首次请求若返回 `"ret":["FAIL_SYS_TOKEN_EMPTY::令牌为空"]` 或 `"FAIL_SYS_TOKEN_EXOIRED"`，从响应 Set-Cookie 抓新 `_m_h5_tk` 重试 1 次。

---

## 6. MTOP 签名实现要点（`signing.py`）

```python
# appKey 固定值（H5 通用）
APP_KEY = "12574478"  # 大麦 H5 appKey（社区逆向值，需在实现时 double check）

def sign(token: str, t: int, app_key: str, data: str) -> str:
    # token = _m_h5_tk.split("_")[0]（前 32 字符）
    raw = f"{token}&{t}&{app_key}&{data}"
    return hashlib.md5(raw.encode()).hexdigest()

# 请求 URL
url = f"https://mtop.damai.cn/h5/{api}/{version}/"
params = {
    "jsv": "2.7.2",
    "appKey": APP_KEY,
    "t": int(time.time() * 1000),
    "sign": sign(token, t, APP_KEY, data_json),
    "type": "originaljson",
    "dataType": "json",
    "v": version,
    "api": api,
    "data": data_json,
}
```

---

## 7. 实施步骤（建议）

### Phase 1：地基（无外网依赖，可 TDD）
- [ ] P1-1 创建 `pyproject.toml` / `README.md` / 目录骨架
- [ ] P1-2 `exceptions.py`（6 类）+ `output.py`（Envelope）+ `formatter.py`（Rich/YAML/JSON）
- [ ] P1-3 `config.py`（env + `~/.damai-cli/config.yaml`）+ `cookies.py`（JSON 持久化 + TTL）
- [ ] P1-4 `signing.py`（纯算法，上单测）
- [ ] P1-5 `cli.py`（Click 骨架，空命令 stub）

### Phase 2：客户端核心
- [ ] P2-1 `client.py`：httpx 封装 + 签名拼 params + `_m_h5_tk` 自刷新 + 指数退避
- [ ] P2-2 `models.py` dataclass + 响应 payload 规范化
- [ ] P2-3 `filter.py` 评分/排序

### Phase 3：登录四件套
- [ ] P3-1 `browser_cookie.py`：browser-cookie3 提取 .damai.cn/.taobao.com
- [ ] P3-2 `qr_login.py`：camoufox 无头 + 终端 QR + 轮询
- [ ] P3-3 `password_login.py`：passport.damai.cn（滑块触发 → 明确失败）
- [ ] P3-4 `auth.py`：三级调度器 + `commands/auth.py`（login/logout/status/whoami）

### Phase 4：只读命令（阅览）
- [ ] P4-1 `commands/reading.py`：search / show / hot / calendar / artist / venue / category
- [ ] P4-2 smoke 测试跑一遍（需真 Cookie）

### Phase 5：账户命令
- [ ] P5-1 `commands/account.py`：favorites / orders / viewers

### Phase 6：交易命令（带护栏）
- [ ] P6-1 `commands/track.py`：开票轮询 + `winotify`（win）/`plyer` 系统通知
- [ ] P6-2 `commands/trade.py`：build（默认 dry-run） + submit（需 `--i-understand-risk`） + pay-url

### Phase 7：文档
- [ ] P7-1 `SKILL.md`（AI 使用指南）+ `SCHEMA.md`（Envelope 契约）+ `CLAUDE.md`
- [ ] P7-2 README（安装/快速开始/示例）

### Phase 8：打包发布
- [ ] P8-1 `pip install -e .` 本地联调
- [ ] P8-2 整体跑一遍 smoke

---

## 8. 合规与免责（必须写进 README）

- 本 CLI 仅供**个人学习研究**，不得用于批量抢票、黄牛、分发
- 所有抢票命令默认 `--dry-run`，实名观演人只能从已绑定列表选
- 写操作走官方 H5 API，**不使用任何绕过风控的手段**（无滑块破解、无 TLS 指纹伪造阿里自有域）
- 遇到 461/471/风控 → 直接退出并提示改用官方 App，不做任何重试/绕过尝试
- 用户需自负账号封禁风险

---

## 9. 待确认

无阻塞问题，等确认后进入 Phase 1。
