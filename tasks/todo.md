# damai-cli 实施进度

> 详细架构、目录结构、签名实现、API 列表见 `CONTRACTS.md`。
> 项目规范见 `CLAUDE.md`。本文件只追踪进度。

---

## Phase 1：地基 ✅
- [x] P1-1 `pyproject.toml` / 目录骨架
- [x] P1-2 `exceptions.py`（15 类）+ `output.py`（Envelope）+ `formatter.py`（Rich/YAML/JSON）
- [x] P1-3 `config.py` + `cookies.py`（JSON 持久化 + 7 天 TTL）
- [x] P1-4 `signing.py`（MTOP md5 签名 + 单测）
- [x] P1-5 `cli.py`（Click 骨架 + 子命令注册）

## Phase 2：客户端核心 ✅
- [x] P2-1 `client.py`：httpx + 签名拼参数 + `_m_h5_tk` 自刷新（限 1 次）+ 指数退避
- [x] P2-2 `models.py` 全部 dataclass（Show/Perform/Sku/Order/Viewer/Artist/Venue）
- [x] P2-3 `filter.py` rank_shows 评分

## Phase 3：登录四件套 ✅
- [x] P3-1 `browser_cookie.py`：browser-cookie3 抓 .damai.cn / .taobao.com
- [x] P3-2 `qr_login.py`：camoufox 无头 + 终端 QR + 轮询
- [x] P3-3 `password_login.py`：passport 表单（滑块直接失败）
- [x] P3-4 `auth.py`：四级调度 + `commands/auth.py`（login/logout/status/whoami）

## Phase 4：只读命令 ✅
- [x] P4-1 `commands/reading.py`：search / show / hot / calendar / artist / venue / category
- [x] P4-2 离线 capture-driven 测试（55/55 绿）

## Phase 5：账户命令 ✅
- [x] P5-1 `commands/account.py`：favorites / orders / viewers
- [ ] P5-2 favorites 真实 API 仍待捕获。**2026-04-26 联网验证**：`mtop.damai.user.myfavorite` 返回 FAIL_SYS_API_NOT_FOUNDED，证实是错误名
- [ ] P5-3 `--status` 选项映射（待空账户外的真实订单 capture）

## Phase 6：交易命令（带护栏）✅
- [x] P6-1 `commands/track.py`：开票轮询 + plyer 系统通知（可选降级）
- [x] P6-2 `commands/trade.py`：build（dry-run）/ submit（`--i-understand-risk`）/ buy / pay-url
- [ ] P6-3 5 路真实 capture 仍 pending：build / submit / buy / pay-url / venue
- [ ] P6-4 venue **2026-04-26 联网验证**：`mtop.damai.mdata.venue.getvenuedetail` 返回 FAIL_SYS_API_NOT_FOUNDED，证实是错误名

## Phase 7：文档 ✅
- [x] P7-1 `CONTRACTS.md`（完整契约）+ `CLAUDE.md`（项目规范）
- [x] P7-2 `README.md`（安装/快速开始/合规免责）+ `SCHEMA.md` + `SKILL.md`

## Phase 8：打包发布 ✅
- [x] P8-1 `pip install -e .` 本地联调
- [x] P8-2 entry_point 测试（`damai --help` 列出所有子命令）

## Phase 9：CI / 工程基建 ✅（本次推进）
- [x] P9-1 `.github/workflows/ci.yml`（py3.10/3.11/3.12 矩阵跑 ruff + mypy + 静态 import + pytest）
- [x] P9-2 mypy 清零（types-PyYAML stub + cast 修源头 Any）
- [x] P9-3 `tests/_integration_check.py` 改作 CI 跑的静态契约检查
- [ ] P9-4 CHANGELOG（待发首版前补）
- [ ] P9-5 GitHub Release / git tag v0.1.0
- [ ] P9-6 PyPI 发布（python -m build + twine upload；建议先 TestPyPI 验证）
- [ ] P9-7 pre-commit hook 配置（可选）

---

## 待外部输入
- **真实流量 capture**：5 路写操作 API + favorites 列表 + 非空订单 / viewers
- **重新登录**：现有 cookies 已 session_expired，需要 `damai login` 后才能验 orders / viewers 链路

## 当前已知约束
- API 服务端搜索接口未抓到真实字段名 → search 复用 list 接口 + 本地 substring 过滤
- channel.artiste 是按品类目录接口，不支持 by-name 全局查询
- 风控 461/471/RGV587/SM_CODE::1999 → 立即退出，不重试，不绕过
