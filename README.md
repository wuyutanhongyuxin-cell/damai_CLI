# damai-cli

大麦网演出阅览与抢票命令行工具（仅供学习研究）。

在终端查看演出信息（搜索 / 详情 / 热门 / 日历）并可选择建单抢票。
**写操作默认 dry-run，必须显式确认才真正提交。**

> 项目仍在迭代，README 待功能稳定后补充完善。

---

## 安装

```bash
pip install -e .            # 基础
pip install -e ".[qr]"      # 含 QR 登录
pip install -e ".[dev]"     # 开发工具
```

## 快速开始

```bash
damai login                                # 登录（优先读浏览器 Cookie）
damai search "五月天"                       # 搜索演出
damai show <itemId>                        # 详情
damai hot                                  # 热门榜
damai track <itemId> --notify              # 开票提醒
damai build <itemId> --perform <P> --sku <S> --viewer <V>
damai submit <build_token> --i-understand-risk
```

输出：TTY → Rich 彩色表格；管道/脚本 → YAML；可加 `--output json` 强制。

---

## 合规免责

**仅供学习研究，禁商用 / 禁黄牛 / 禁批量抢票。**

- 写操作默认 **dry-run**，需 `--i-understand-risk` 才真正提交
- 遇风控（461 / 471 / 滑块）立即退出，**不绕过任何风控机制**
- 实名观演人只能从已绑定列表选择
- 详细协议见 [LICENSE](LICENSE)；后果由用户自负
