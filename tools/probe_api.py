"""直接调一个 MTOP api 打印 raw 响应，用于诊断字段结构。

跑法：E:/python/python_3.13/python.exe tools/probe_api.py <api> <version> <data_json>

示例：
  probe_api.py mtop.damai.wireless.search.search 1.0 '{"keyword":"周杰伦","pageSize":3}'
  probe_api.py mtop.damai.item.detail.getdetail 1.0 '{"itemId":"123456"}'
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from damai_cli.client import MtopClient
from damai_cli.cookies import CookieJar


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    api = sys.argv[1]
    version = sys.argv[2]
    data_str = sys.argv[3] if len(sys.argv) > 3 else "{}"
    try:
        data = json.loads(data_str)
    except json.JSONDecodeError as e:
        print(f"[ERROR] data 不是合法 JSON: {e}")
        sys.exit(1)

    jar = CookieJar()
    jar.load()
    with MtopClient(jar) as client:
        try:
            raw = client.request(api, version, data)
        except Exception as e:
            # 异常消息可能含中文（如 FAIL_SYS_BIZPARAM_MISSED::缺少...），Windows GBK 打印会崩
            _safe_print(f"[ERROR] {type(e).__name__}: {e}")
            return
        dump = json.dumps(raw, ensure_ascii=False, indent=2, default=str)
        out_path = Path("tmp_probe_" + api.replace(".", "_") + ".json")
        out_path.write_text(dump, encoding="utf-8")
        print(f"[OK] 响应 {len(dump)} 字节已保存到 {out_path}")
        print("---TOP-LEVEL KEYS---")
        if isinstance(raw, dict):
            for k in raw.keys():
                v = raw[k]
                tp = type(v).__name__
                size = len(v) if hasattr(v, "__len__") else "-"
                print(f"  {k}: {tp} (len={size})")
        # 若响应里第一层就有 list 字段，打出其第一个元素的 keys（判断 schema）
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"---{k}[0] KEYS---")
                    for kk in v[0].keys():
                        print(f"  {kk}")
                    break


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


if __name__ == "__main__":
    main()
