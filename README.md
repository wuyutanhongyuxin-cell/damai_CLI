# damai-cli

大麦网演出阅览与抢票命令行工具（仅供学习研究）。

在终端查看演出信息（搜索 / 详情 / 热门 / 日历 / 艺人）并可选择建单抢票。
**写操作默认 dry-run，必须显式确认才真正提交。**

[![CI](https://github.com/wuyutanhongyuxin-cell/damai_CLI/actions/workflows/ci.yml/badge.svg)](https://github.com/wuyutanhongyuxin-cell/damai_CLI/actions/workflows/ci.yml)

---

## 安装

```bash
pip install damai-cli                # 基础（PyPI 上线后）
pip install -e .                     # 源码本地安装
pip install -e ".[qr]"               # 含 camoufox QR 登录
pip install -e ".[dev]"              # 开发工具（pytest/ruff/mypy）
```

要求 Python ≥ 3.10。

## 快速开始

```bash
damai login                          # 优先读浏览器 Cookie；失败回落 QR / 密码
damai status                         # 查看登录态 + cookie 过期时间
damai search "五月天" --limit 10      # 搜索演出
damai show <itemId>                  # 详情（场次/价位/座位图）
damai hot --city 852                 # 热门榜
damai calendar --city 852            # 近期演出
damai artist --group-id 2394         # 列演唱会品类全部艺人
damai category                       # 拉动态分类列表
```

输出方向：
- TTY → Rich 彩色表格（默认）
- 管道/脚本 → YAML（自动探测）
- 强制：`damai --output {rich|yaml|json} <cmd>`

## 命令一览

| 类型 | 命令 | 说明 |
|------|------|------|
| 阅览 | `search` `show` `hot` `calendar` `artist` `venue` `category` | 演出查询 |
| 账户 | `login` `logout` `status` `whoami` `favorites` `orders` `viewers` | 登录与个人数据 |
| 监控 | `track <itemId> --notify` | 开票轮询 + 系统通知 |
| 交易 | `build` `submit` `buy` `pay-url` | 写操作（默认 dry-run） |

完整子命令选项：`damai <cmd> --help`。退出码：0=成功，1=错误（详见 stderr 的 envelope code）。

## 风险护栏

- 所有写操作命令默认只打印 payload，不真正提交
- `submit` 必须显式 `--i-understand-risk` 才会调 `mtop.trade.order.create.h5`
- 实名观演人只能从 `damai viewers` 已绑定列表选择，不允许新建
- 风控信号（461 / 471 / `RGV587_ERROR` / `SM_CODE::1999`）→ 立即退出，不重试，不绕过
- 不使用滑块破解、不伪造阿里自有域 TLS 指纹、不引入第三方验证码服务

## 故障排除

| 现象 | 处理 |
|------|------|
| `session_expired` | 重跑 `damai login`（即使 `damai status` 显示 logged_in，服务端 session 也可能已失效） |
| `FAIL_SYS_API_NOT_FOUNDED` | API 名错；该端点未捕获到真实流量。详见 `CONTRACTS.md` 中的 pending capture 列表 |
| 风控触发 | 立即停手，改用官方大麦 App 完成；本工具不会尝试绕过 |
| Cookie 7 天 TTL | `damai status` 看到 `expires_at`；过期需重新登录 |

## 开发

```bash
pip install -e ".[dev]"
ruff check damai_cli tests
mypy damai_cli
pytest -q                            # 默认跳过 smoke
pytest -m smoke                      # 真实网络（需有效 cookie）
python tests/_integration_check.py   # 静态 import 契约检查
```

## 合规免责

**仅供学习研究，禁商用 / 禁黄牛 / 禁批量抢票。** 完整条款见 [LICENSE](LICENSE)。
后果由用户自负；详细模块契约见 [CONTRACTS.md](CONTRACTS.md)，输出 envelope 见 [SCHEMA.md](SCHEMA.md)。
