from __future__ import annotations

import os
import sys

import click

from . import __version__


@click.group(name="damai")
@click.version_option(__version__, prog_name="damai")
@click.option(
    "--output",
    type=click.Choice(["rich", "yaml", "json"]),
    envvar="OUTPUT",
    default=None,
    help="输出格式（覆盖自动探测）",
)
@click.option("--verbose", is_flag=True, default=False, help="打印调试信息")
@click.pass_context
def cli(ctx: click.Context, output: str | None, verbose: bool) -> None:
    # output 写入环境变量供 output.detect_mode() 读取
    if output:
        os.environ["OUTPUT"] = output
    if verbose:
        os.environ["DAMAI_VERBOSE"] = "1"


def _try_register(module_name: str) -> None:
    # 优雅降级：子模块文件缺失(ImportError)或尚未实现 register(AttributeError) 时打警告
    try:
        from importlib import import_module
        mod = import_module(f".commands.{module_name}", package=__package__ or "damai_cli")
        mod.register(cli)
    except (ImportError, AttributeError) as exc:
        print(
            f"[damai-cli] 警告：commands.{module_name} 尚未实现，已跳过 ({exc})",
            file=sys.stderr,
        )


# 按顺序注册；reading 已实现，其余走降级路径
for _mod in ("auth", "reading", "account", "track", "trade"):
    _try_register(_mod)


if __name__ == "__main__":
    cli()
