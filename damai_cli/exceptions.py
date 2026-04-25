from __future__ import annotations


# 基类：所有大麦 CLI 异常的统一入口
class DamaiError(Exception):
    code: str = "upstream_error"

    def __init__(self, message: str = "", **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra

    def __str__(self) -> str:
        return self.message


# --- 认证相关 ---
class NotAuthenticated(DamaiError):
    code = "not_authenticated"


class SessionExpired(DamaiError):
    code = "session_expired"


class TokenEmpty(DamaiError):
    # mtop 返回 FAIL_SYS_TOKEN_EMPTY 且重签失败
    code = "token_empty"


# --- 签名 / 风控 ---
class SignFailed(DamaiError):
    code = "sign_failed"


class NeedSlideCaptcha(DamaiError):
    # RGV587_ERROR / 滑块验证
    code = "need_slide_captcha"


class IpBlocked(DamaiError):
    # SM_CODE::1999 风控
    code = "ip_blocked"


class RateLimited(DamaiError):
    # HTTP 429 / FAIL_SYS_USER_FLOW_LIMIT
    code = "rate_limited"


# --- 票务业务 ---
class ItemSoldOut(DamaiError):
    code = "item_sold_out"


class ItemNotStarted(DamaiError):
    code = "item_not_started"


class RealNameRequired(DamaiError):
    code = "real_name_required"


# --- 通用错误 ---
class NetworkError(DamaiError):
    # httpx 网络层异常
    code = "network_error"


class UpstreamError(DamaiError):
    # mtop FAIL_SYS_* 兜底
    code = "upstream_error"


class NotFound(DamaiError):
    code = "not_found"


class InvalidInput(DamaiError):
    code = "invalid_input"


class Unsupported(DamaiError):
    code = "unsupported"
