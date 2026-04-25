---
name: damai-cli
description: 大麦网演出阅览与抢票 CLI，供 AI Agent 在终端查询演出信息、监控开票、建单抢票。调用 damai 命令完成搜索演出、查看详情、track 开票通知、建单提单等任务。
author: damai-cli contributors
version: "0.1.0"
tags:
  - damai
  - 大麦网
  - 演出
  - 抢票
  - cli
---

# damai-cli — AI Agent 操作手册

## 项目定位

大麦网演出阅览与抢票 CLI，给开发者在终端查询演出信息、监控开票、建单抢票用。

## 安装与调用入口

```bash
# 安装（需要 Python 3.10+）
uv tool install damai-cli
# 或
pip install damai-cli

# 主命令入口
damai --help
damai --version

# 可选扩展
pip install "damai-cli[qr]"   # QR 登录需要 camoufox
pip install "damai-cli[tls]"  # curl_cffi TLS 指纹支持
```

## 认证前置检查

在执行任何需要登录的命令前，先确认登录态：

```bash
damai status --output yaml
# ok: true 且 data.logged_in: true → 已登录
# ok: true 且 data.logged_in: false → 需要先执行 damai login
```

## 核心命令速查表

### auth — 认证管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `damai login [--method auto\|browser\|qr\|password]` | 登录大麦账号 | `damai login --method qr` |
| `damai logout` | 清除本地 Cookie | `damai logout` |
| `damai status` | 查看登录状态 | `damai status --output yaml` |
| `damai whoami` | 显示当前账号信息 | `damai whoami --output json` |

登录方式说明：
- `auto`（默认）：依次尝试 saved → browser → qr，不含 password
- `browser`：从本地浏览器（Chrome/Edge/Firefox/Brave）提取 Cookie
- `qr`：终端显示 ASCII 二维码，扫码登录（需 `[qr]` 扩展）
- `password`：账号密码登录，遇滑块验证码直接报错，需显式指定

### reading — 演出阅览

| 命令 | 说明 | 示例 |
|------|------|------|
| `damai search <keyword> [--limit N] [--city X] [--category Y]` | 关键词搜索演出 | `damai search "周杰伦" --city 上海 --limit 10` |
| `damai show <item_id>` | 查看演出详情（含场次和票档） | `damai show 12345678` |
| `damai hot [--city X]` | 热门演出榜单 | `damai hot --city 北京` |
| `damai calendar [--city X] [--days 7]` | 近期演出日历 | `damai calendar --city 广州 --days 14` |
| `damai artist <name>` | 查看艺人及其演出 | `damai artist "薛之谦"` |
| `damai venue <id>` | 查看场馆及演出 | `damai venue V_001` |
| `damai category` | 查看演出分类和地区列表 | `damai category --output yaml` |

### account — 账号数据

| 命令 | 说明 | 示例 |
|------|------|------|
| `damai favorites` | 已收藏的演出 | `damai favorites --output json` |
| `damai orders [--status pending\|paid\|refunded]` | 订单列表 | `damai orders --status paid` |
| `damai viewers` | 已绑定的实名观演人列表 | `damai viewers --output yaml` |

### track — 开票监控

| 命令 | 说明 | 示例 |
|------|------|------|
| `damai track <item_id> --perform <id> [--notify] [--interval 30]` | 轮询开票状态，status 变 on_sale 时弹通知 | `damai track 12345678 --perform P_001 --notify --interval 60` |

说明：
- `--notify` 触发系统桌面通知（需要 plyer）
- `--interval`：轮询间隔秒数，默认 30s
- track 命令输出 `triggered: true` 后即可执行 build/buy 流程

### trade — 建单与购票

| 命令 | 说明 | 示例 |
|------|------|------|
| `damai build <item_id> --perform X --sku Y --viewer Z [--count 1]` | 建单预览（输出 build_token + 订单摘要） | `damai build 12345678 --perform P_001 --sku S_01 --viewer V_001` |
| `damai submit <build_token> [--i-understand-risk]` | 提交订单；无 flag 时为 dry-run | `damai submit TOKEN --i-understand-risk` |
| `damai buy <item_id> --perform X --sku Y --viewer Z [--auto-submit] [--i-understand-risk]` | build + submit 一步完成 | `damai buy 12345678 --perform P_001 --sku S_01 --viewer V_001 --i-understand-risk` |
| `damai pay-url <order_id>` | 获取已创建订单的支付链接 | `damai pay-url ORDER_001` |

写操作护栏：
- `build` 默认只预览，不发请求
- `submit` 和 `buy` 无 `--i-understand-risk` 时均为 dry-run，仅打印 payload
- viewer 只能从 `damai viewers` 返回的已绑定列表中选择

## 输出模式约定

```bash
# rich（默认 TTY）：彩色表格/面板，适合人工查看
damai search "演唱会"

# yaml（默认非 TTY）：机器友好，token 紧凑，AI Agent 推荐
damai search "演唱会" --output yaml

# json：jq 处理时使用
damai search "演唱会" --output json

# 环境变量全局覆盖
OUTPUT=yaml damai search "演唱会"
OUTPUT=json damai hot
```

切换优先级：`--output` 参数 > `OUTPUT` 环境变量 > TTY 自动检测（TTY→rich，非 TTY→yaml）

所有输出均使用 Envelope 格式，参见 SCHEMA.md。

## 典型任务示例

### 示例 1：搜索演出

```bash
# 搜索上海的周杰伦演唱会，取前 5 条
damai search "周杰伦" --city 上海 --limit 5 --output yaml
# 从 data.shows[0].id 取 item_id 用于后续命令
```

### 示例 2：查看演出详情

```bash
# 查看演出的场次（performs）和票档（skus）
damai show 12345678 --output yaml
# data.performs 列出各场次 perform_id
# data.skus 列出各票档 sku_id 和价格
```

### 示例 3：track 开票监控

```bash
# 每 60 秒轮询一次，开票后弹桌面通知
damai track 12345678 --perform P_001 --notify --interval 60 --output yaml
# triggered: true 后立即执行 build 命令
```

### 示例 4：建单（build）

```bash
# 先获取观演人列表
damai viewers --output yaml
# 用 viewer_id 建单，先预览不提交
damai build 12345678 --perform P_001 --sku S_01 --viewer V_001 --count 1 --output yaml
# 确认 data.preview 信息无误后再 submit
```

### 示例 5：查看订单

```bash
# 查看全部已支付订单
damai orders --status paid --output yaml
# 获取支付链接（如订单未支付）
damai pay-url ORDER_001 --output yaml
```

## 错误码处理建议

| 错误码 | 建议处置 |
|--------|----------|
| `not_authenticated` | 执行 `damai login`；推荐先用 `--method browser`，失败再改 `--method qr` |
| `session_expired` | Cookie 已过期，执行 `damai login` 刷新；不要重试原请求 |
| `sign_failed` | 签名计算失败，通常是 `_m_h5_tk` 为空；退出后重新登录 |
| `need_slide_captcha` | 遭遇滑块验证码，不要尝试绕过；提示用户到大麦 App 完成验证后再试 |
| `ip_blocked` | IP 被风控（SM_CODE::1999），提示用户切换网络（热点/VPN），不要重试 |
| `rate_limited` | 请求频率超限，客户端已按指数退避重试（5/10/20/30s），仍失败则停止并等待数分钟 |
| `item_sold_out` | 票档已售罄；可切换其他 sku_id 或使用 track 命令等待补票 |
| `item_not_started` | 未到开售时间；使用 `damai track` 监控开票 |
| `real_name_required` | 需要实名认证；提示用户到大麦 App 完成实名认证 |
| `network_error` | 网络异常；检查网络后重试，使用指数退避，最多重试 3 次 |
| `upstream_error` | 大麦 API 返回未预期错误；记录错误详情，短暂等待后重试 1 次 |
| `not_found` | 演出/场次/订单不存在；检查 item_id/perform_id 是否正确 |
| `invalid_input` | 参数错误；检查 item_id/sku_id/viewer_id 格式和范围 |
| `unsupported` | 当前环境不支持该操作（如 QR 登录未安装 camoufox）；安装对应 extra |
| `token_empty` | `_m_h5_tk` 为空，客户端已自动重取 token 重试 1 次；仍失败则重新登录 |

## 合规声明

- 禁止使用本工具自动抢票后分发转售，违反大麦网服务条款及相关法律
- 禁止绕过风控：不使用滑块破解、不伪造 TLS 指纹、不引入第三方验证码服务
- 写操作（build/submit/buy）均有 dry-run 保护，必须显式加 `--i-understand-risk` 才真实下单
- 遭遇风控信号（461/471/RGV587_ERROR/SM_CODE::1999）时立即退出，不做任何重试
