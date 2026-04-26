from __future__ import annotations

import functools
import sys

from ..exceptions import DamaiError, NotAuthenticated
from ..output import emit, err, ok


def run_command(handler):
    # 统一包裹 try/except + emit；非零码退出
    @functools.wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            result = handler(*args, **kwargs)
            # handler 已返回完整 envelope 则直接 emit，否则包装成 ok
            if isinstance(result, dict) and result.get("ok") in (True, False):
                emit(result)
            else:
                emit(ok(result))
        except NotAuthenticated as e:
            emit(err(e.code, str(e) or "请先 damai login"))
            sys.exit(2)
        except DamaiError as e:
            emit(err(e.code, str(e), **e.extra))
            sys.exit(1)
    return wrapper


def get_client(need_login: bool = False):
    # 延迟导入避免循环；need_login=True 时校验 cookie 状态
    from ..client import MtopClient
    from ..cookies import CookieJar

    jar = CookieJar()
    if need_login and not jar.is_logged_in():
        raise NotAuthenticated("请先 damai login")
    return MtopClient(cookies=jar)
