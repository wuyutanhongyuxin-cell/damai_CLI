# CLAUDE.md — damai-cli 项目规范

> Claude Code 每次启动自动读取本文件。硬限制不可绕过。

---

## [项目专属区域]

### 项目名称
damai-cli

### 一句话描述
大麦网演出阅览与抢票 CLI，给开发者在终端查询演出信息、监控开票、建单抢票用。

### 技术栈
- 语言：Python 3.10+，使用 `from __future__ import annotations`
- CLI 框架：click >= 8.1
- HTTP：httpx >= 0.27（可选 curl_cffi TLS 指纹）
- 输出：rich >= 13.7 + pyyaml >= 6（三级输出 rich/yaml/json + Envelope）
- 签名：自实现 MTOP md5 签名（signing.py）
- 登录：browser-cookie3 / camoufox QR / passport 表单
- 构建：hatchling
- 测试：pytest + pytest-asyncio，默认跳过 smoke

### 项目结构
```
damai-cli/
├── pyproject.toml          # 构建配置、依赖、pytest/ruff/mypy 设置
├── README.md               # 安装、快速开始、合规免责
├── CLAUDE.md               # 本文件，AI 规范
├── CONTRACTS.md            # 模块契约（不可改动）
├── .gitignore
├── tasks/todo.md           # 实施规划与进度
├── damai_cli/
│   ├── __init__.py         # 只有 __version__
│   ├── cli.py              # Click 入口 + 子命令注册
│   ├── client.py           # httpx MTOP 封装 + 重试
│   ├── signing.py          # _m_h5_tk 签名算法
│   ├── cookies.py          # Cookie 持久化 + TTL
│   ├── auth.py             # 四级登录调度器
│   ├── qr_login.py         # camoufox QR 流程
│   ├── password_login.py   # passport 表单（遇滑块直接失败）
│   ├── browser_cookie.py   # browser-cookie3 封装
│   ├── exceptions.py       # 15 类异常
│   ├── formatter.py        # Rich 渲染（table/detail/list）
│   ├── output.py           # Envelope ok/err/emit
│   ├── config.py           # 目录路径 + env 读取
│   ├── filter.py           # 演出过滤与评分
│   ├── models.py           # dataclass（Show/Perform/Sku 等）
│   └── commands/
│       ├── __init__.py     # 空
│       ├── _common.py      # run_command 装饰器 + get_client
│       ├── auth.py         # login/logout/status/whoami
│       ├── reading.py      # search/show/hot/calendar/artist/venue/category
│       ├── account.py      # favorites/orders/viewers
│       ├── track.py        # 开票轮询 + 系统通知
│       └── trade.py        # build/submit/buy/pay-url（写操作）
└── tests/
    ├── __init__.py
    ├── conftest.py         # 通用 fixture + smoke marker
    ├── test_signing.py
    ├── test_cookies.py
    └── test_output.py
```

### 当前阶段
Phase 1（地基）进行中。参见 `tasks/todo.md`。

---

## damai 专属硬规则（不可违反）

### 写操作护栏
1. **所有写操作默认 dry-run**：build / submit / buy 命令在没有 `--i-understand-risk` 时，只打印即将发送的 payload，不真正发送请求
2. **`submit` 必须持有 `--i-understand-risk` flag** 才允许调用 `mtop.trade.order.create.h5`
3. 实名观演人只能从账户 `damai viewers` 返回的已绑定列表中选择，不允许新建

### 风控规则
4. **遇风控立即退出**：响应 code 含 461 / 471 / `RGV587_ERROR` / `SM_CODE::1999` 等风控信号时，打印提示 "遭遇风控，请改用官方大麦 App" 后退出，**不做任何重试**
5. **禁止使用反风控手段**：不使用滑块破解、不伪造 TLS 指纹以绕过阿里自有域、不引入任何第三方验证码服务
6. **`_m_h5_tk` 自刷新限一次**：TOKEN_EMPTY / TOKEN_EXPIRED 时从 Set-Cookie 拿新 token 重签重试仅 1 次，仍失败则 raise，不循环

### 代码质量
7. **不联网**：实现时不调用 WebFetch / WebSearch，按 CONTRACTS.md 实现
8. **契约不可改**：发现 CONTRACTS.md 有问题只在汇报中指出，不擅自修改
9. `from __future__ import annotations` 每个 .py 文件必须有
10. 中文注释只在 why 不明显处写，不要堆砌 docstring

---

## 文件行数硬限制

| 文件类型 | 最大行数 | 超限动作 |
|----------|----------|----------|
| 单个源代码文件 | **200 行** | 立即拆分 |
| 单个模块目录 | **2000 行** | 拆分子模块 |
| 测试文件 | **300 行** | 按功能拆分 |
| 配置文件 | **100 行** | 拆分配置 |

每次创建或修改文件后检查行数，接近限制时主动提醒。

---

## 定期清理触发词

当用户说以下关键词时，执行对应动作：

| 关键词 | 动作 |
|--------|------|
| "清理一下" | 行数审计 + 死代码检测 + TODO 清理 + 描述同步 |
| "拆一下" | 检查指定文件行数，给出拆分方案 |
| "健康检查" | 运行完整项目健康度检查 |
| "现在到哪了" | 总结当前进度，参考 tasks/todo.md |
| "省着点" | 回复更简短，不重复输出完整文件 |
| "全力跑" | 并行执行，大改，不每步确认 |

---

## Sub-Agent 并行调度规则

**并行派遣**（同时满足）：3+ 个不相关任务 / 不操作同一文件 / 无 I/O 依赖  
**顺序派遣**（任一触发）：B 需要 A 的输出 / 操作同一文件 / 范围不明确

每次派遣 sub-agent 必须注明：操作文件（写）/ 读取文件（只读）/ 完成标准 / 禁碰文件。

---

## 编码规范

- 所有外部调用（API / 文件 IO）必须 try-except，失败时友好提示不崩溃
- 单函数 ≤ 30 行，函数名动词开头
- 不自行引入新依赖，需要新库先与用户确认
- 敏感信息通过环境变量读取，不硬编码

---

## Git 规范

Commit 格式：`<类型>: <一句话描述>`  
类型：`feat` / `fix` / `refactor` / `docs` / `chore`

提交前确认：无 .env / __pycache__ / cookies.json 混入。

---

## 沟通规范

- 不确定时直接说不确定，给 2-3 个方案让用户选
- 任务太大时先给拆分计划（5-8 步），确认后逐步执行
- 代码出问题：先说是什么问题 → 再说原因 → 最后给修复方案
- 对话超 20 轮后建议 `/compact` 压缩上下文
