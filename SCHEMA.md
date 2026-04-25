# damai-cli 输出契约（SCHEMA）

目标读者：AI Agent，用于解析 `damai` 命令的 stdout。

## Envelope 格式

所有命令（`--output yaml` 或 `--output json`）均输出以下 Envelope，非 TTY 环境默认 YAML。

### 成功态

```yaml
ok: true
schema_version: "1"
data: ...           # 各命令具体结构见下文
pagination:         # 可选，列表命令才有
  total: 100
  page: 1
  page_size: 20
```

### 错误态

```yaml
ok: false
schema_version: "1"
error:
  code: not_authenticated
  message: 请先执行 damai login
  # 可能有附加字段，如 retry_after（rate_limited 时）
```

解析建议：先判断 `ok` 字段，`ok: false` 时读 `error.code` 分支处理，不要直接访问 `data`。

---

## 各命令 data 结构

### search / hot / calendar

```yaml
data:
  shows:
    - id: "12345678"
      name: "周杰伦演唱会 2025"
      city: "上海"
      venue: "上海体育场"
      category: "演唱会"
      price_min: 380.0
      price_max: 1580.0
      status: "on_sale"         # on_sale / pre_sale / ended
      start_time: "2025-08-01T20:00:00+08:00"
      poster_url: "https://..."
```

### show

```yaml
data:
  id: "12345678"
  name: "周杰伦演唱会 2025"
  city: "上海"
  venue: "上海体育场"
  category: "演唱会"
  price_min: 380.0
  price_max: 1580.0
  status: "on_sale"
  start_time: "2025-08-01T20:00:00+08:00"
  poster_url: "https://..."
  performs:
    - perform_id: "P_001"
      show_id: "12345678"
      start_time: "2025-08-01T20:00:00+08:00"
      venue: "上海体育场"
      seat_map_url: "https://..."
  skus:
    - sku_id: "S_01"
      perform_id: "P_001"
      price: 580.0
      description: "内场站票"
      stock_status: "available"   # available / low_stock / sold_out
```

### artist

```yaml
data:
  artist:
    id: "A_001"
    name: "薛之谦"
    follower_count: 8000000
    upcoming_count: 3
  shows:
    - # Show 结构，同 search
```

### venue

```yaml
data:
  venue:
    id: "V_001"
    name: "国家大剧院"
    city: "北京"
    address: "北京市西城区西长安街2号"
    capacity: 5452
  shows:
    - # Show 结构，同 search
```

### category

```yaml
data:
  categories:
    - id: "cat_1"
      name: "演唱会"
    - id: "cat_2"
      name: "音乐节"
  regions:
    - id: "reg_1"
      name: "上海"
    - id: "reg_2"
      name: "北京"
```

### favorites

```yaml
data:
  shows:
    - # Show 结构，同 search
```

### orders

```yaml
data:
  orders:
    - order_id: "ORDER_001"
      show_name: "周杰伦演唱会 2025"
      perform_time: "2025-08-01T20:00:00+08:00"
      status: "paid"           # pending / paid / refunded / cancelled
      total_fee: 580.0
      pay_url: "https://..."   # 未支付时有值，已支付可能为 null
```

### viewers

```yaml
data:
  viewers:
    - viewer_id: "V_001"
      name: "张三"
      cert_type: "身份证"
      cert_no_masked: "310***********1234"
```

### track

```yaml
data:
  item_id: "12345678"
  status: "on_sale"          # 最新轮询到的演出状态
  checked_at: "2025-07-01T10:30:00+08:00"
  triggered: true            # true 表示本次轮询检测到开售
```

### build

```yaml
data:
  build_token: "BUILD_TOKEN_XXXXX"
  preview:
    show_name: "周杰伦演唱会 2025"
    perform_time: "2025-08-01T20:00:00+08:00"
    sku_desc: "内场站票"
    count: 1
    total_fee: 580.0
    viewers:
      - name: "张三"
        cert_no_masked: "310***********1234"
```

### submit

正式提交（含 `--i-understand-risk`）：

```yaml
data:
  order_id: "ORDER_001"
  pay_url: "https://pay.damai.cn/..."
```

dry-run（无 `--i-understand-risk`）：

```yaml
data:
  dry_run: true
  payload:
    build_token: "BUILD_TOKEN_XXXXX"
    # 其他将发送的字段
  pay_url_preview: "https://pay.damai.cn/..."
```

### buy

build + submit 合并结果，结构同 submit（正式提交时返回 order_id + pay_url）。

### pay-url

```yaml
data:
  order_id: "ORDER_001"
  pay_url: "https://pay.damai.cn/..."
```

### login / status / whoami

```yaml
data:
  logged_in: true
  user_id: "u_123456"
  nickname: "大麦用户"
  method: "browser"          # login 命令才有：browser / qr / password / saved
  expires_at: "2025-07-08T10:00:00+08:00"   # 可能为 null
```

---

## Dataclass 字段表

### Show

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `id` | string | 演出唯一 ID（item_id） | 否 |
| `name` | string | 演出名称 | 否 |
| `city` | string | 所在城市 | 是 |
| `venue` | string | 场馆名称 | 是 |
| `category` | string | 演出分类 | 是 |
| `price_min` | float | 最低票价（元） | 是 |
| `price_max` | float | 最高票价（元） | 是 |
| `status` | string | 售票状态：on_sale / pre_sale / ended | 是 |
| `start_time` | string | 首场开始时间，ISO 8601 | 是 |
| `poster_url` | string | 海报图片 URL | 是 |

### Perform

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `perform_id` | string | 场次 ID | 否 |
| `show_id` | string | 所属演出 ID | 否 |
| `start_time` | string | 场次开始时间，ISO 8601 | 是 |
| `venue` | string | 场馆名称 | 是 |
| `seat_map_url` | string | 座位图 URL | 是 |

### Sku

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `sku_id` | string | 票档 ID | 否 |
| `perform_id` | string | 所属场次 ID | 否 |
| `price` | float | 票价（元） | 否 |
| `description` | string | 票档描述（如"内场 A 区"） | 是 |
| `stock_status` | string | 库存状态：available / low_stock / sold_out | 是 |

### Viewer

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `viewer_id` | string | 观演人 ID | 否 |
| `name` | string | 姓名 | 否 |
| `cert_type` | string | 证件类型（如"身份证"） | 是 |
| `cert_no_masked` | string | 脱敏证件号 | 是 |

### Order

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `order_id` | string | 订单 ID | 否 |
| `show_name` | string | 演出名称 | 否 |
| `perform_time` | string | 场次时间，ISO 8601 | 是 |
| `status` | string | 订单状态：pending / paid / refunded / cancelled | 是 |
| `total_fee` | float | 订单总金额（元） | 是 |
| `pay_url` | string | 支付链接（未支付时有效） | 是 |

### Artist

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `id` | string | 艺人 ID | 否 |
| `name` | string | 艺人名称 | 否 |
| `follower_count` | int | 关注人数 | 是 |
| `upcoming_count` | int | 未来演出场次数 | 是 |

### Venue

| 字段 | 类型 | 含义 | 可为空 |
|------|------|------|--------|
| `id` | string | 场馆 ID | 否 |
| `name` | string | 场馆名称 | 否 |
| `city` | string | 所在城市 | 是 |
| `address` | string | 详细地址 | 是 |
| `capacity` | int | 场馆容量（座位数） | 是 |

---

## 错误码表

| code | message 示例 | 建议处置 |
|------|-------------|----------|
| `not_authenticated` | 请先执行 damai login | 执行 `damai login`，优先 browser 方式 |
| `session_expired` | 登录态已过期 | 重新执行 `damai login`，不要重试原请求 |
| `sign_failed` | _m_h5_tk 签名失败 | 退出后重新登录，`_m_h5_tk` 可能丢失 |
| `need_slide_captcha` | 需要完成滑块验证 | 提示用户去大麦 App 完成验证，不要绕过 |
| `ip_blocked` | IP 被风控，请更换网络 | 切换网络后重试，不要在同 IP 继续轮询 |
| `rate_limited` | 请求频率过高 | 等待 retry_after 秒（已指数退避），不要立即重试 |
| `item_sold_out` | 票档已售罄 | 换其他 sku_id，或用 track 命令等待补票 |
| `item_not_started` | 演出尚未开始售票 | 用 `damai track` 监控开售 |
| `real_name_required` | 购票需要实名认证 | 提示用户到大麦 App 完成实名 |
| `network_error` | 网络请求失败 | 检查网络，指数退避后最多重试 3 次 |
| `upstream_error` | 大麦接口返回异常 | 记录 extra 字段详情，等待后重试 1 次 |
| `not_found` | 演出/场次/订单不存在 | 检查 item_id/perform_id/order_id 是否有误 |
| `invalid_input` | 参数格式错误 | 检查命令参数类型和取值范围 |
| `unsupported` | 当前环境不支持该操作 | 安装对应 extra，如 `pip install damai-cli[qr]` |
| `token_empty` | _m_h5_tk 为空 | 客户端已自动重取 token 重试 1 次，仍失败则重新登录 |
