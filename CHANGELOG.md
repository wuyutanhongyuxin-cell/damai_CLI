# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式与 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0] - 2026-04-26

首版发布。完成 Phase 1-9 全部计划。

### 新增
- **阅览类命令**：`search` / `show` / `hot` / `calendar` / `artist` / `venue` / `category`
- **账户类命令**：`login` / `logout` / `status` / `whoami` / `favorites` / `orders` / `viewers`
- **交易类命令（带护栏）**：`track` / `build` / `submit` / `buy` / `pay-url`
- **MTOP 签名核心**：`signing.py` 自实现 `_m_h5_tk` md5 签名 + token 自刷新（限 1 次）
- **四级登录调度**：缓存 cookie → browser-cookie3 → camoufox QR → passport 表单
- **Envelope 输出**：rich/yaml/json 三级输出 + `ok` / `err` 统一封装
- **风控护栏**：461/471/RGV587/SM_CODE::1999 立即退出；写操作默认 dry-run；submit 需 `--i-understand-risk`
- **离线测试 55 项**：基于 capture 的端点解析全覆盖

### 工程
- GHA CI（py3.10/3.11/3.12 矩阵）：ruff + mypy + 静态 import 契约 + pytest
- 静态 import 契约脚本（`tests/_integration_check.py`）
- `LicenseRef-Study-Research-Only` 自定义 SPDX：禁商用 / 禁黄牛 / 禁绕风控

### 已知 pending capture
- `favorites` 列表 API 仍是猜测值（已抓 `my.content.get` 仅有计数）
- `venue` / `trade.build` / `trade.submit` / `trade.buy` / `trade.pay-url` 5 路写操作未抓到真实流量
- `orders --status` 选项未映射

[Unreleased]: https://github.com/wuyutanhongyuxin-cell/damai_CLI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wuyutanhongyuxin-cell/damai_CLI/releases/tag/v0.1.0
