"""静态 import 契约检查：扫 damai_cli 下所有文件，验证跨模块 from-import 的名字真实存在。"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "damai_cli"
PKG = "damai_cli"

def exports_of(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                names.add(alias.asname or alias.name)
        elif isinstance(n, ast.Import):
            for alias in n.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names

def resolve(mod: str, level: int, current: pathlib.Path) -> pathlib.Path | None:
    if level == 0 and not mod.startswith(PKG):
        return None
    if level > 0:
        base = current.parent
        for _ in range(level - 1):
            base = base.parent
        target_rel = mod.replace(".", "/") if mod else ""
    else:
        rel = mod[len(PKG) + 1:] if mod.startswith(PKG + ".") else ""
        base = ROOT
        target_rel = rel.replace(".", "/")
    cand = base / (target_rel + ".py") if target_rel else base / "__init__.py"
    if cand.exists():
        return cand
    pkg_init = (base / target_rel / "__init__.py") if target_rel else None
    if pkg_init and pkg_init.exists():
        return pkg_init
    return None

def main() -> int:
    errors: list[str] = []
    files = list(ROOT.rglob("*.py"))
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None and node.level == 0:
                    continue
                # from . import X → X 是兄弟子模块名，分别 resolve 每个 alias
                if node.module is None and node.level > 0:
                    pkg_init = resolve("", node.level, f)
                    pkg_exports = exports_of(pkg_init) if pkg_init else set()
                    for alias in node.names:
                        if resolve(alias.name, node.level, f) is None and alias.name not in pkg_exports:
                            errors.append(f"{f.relative_to(ROOT.parent)}:{node.lineno} submodule/name {alias.name} not found")
                    continue
                target = resolve(node.module or "", node.level, f)
                if target is None:
                    continue
                exp = exports_of(target)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if alias.name not in exp:
                        errors.append(f"{f.relative_to(ROOT.parent)}:{node.lineno} imports {alias.name} from {node.module or '.'} (level={node.level}) not found in {target.relative_to(ROOT.parent)}")
    if errors:
        print(f"FAIL: {len(errors)} issue(s)")
        for e in errors:
            print("  -", e)
        return 1
    print(f"OK: {len(files)} files, all cross-module from-imports resolved")
    return 0

if __name__ == "__main__":
    sys.exit(main())
