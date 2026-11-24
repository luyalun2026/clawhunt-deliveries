"""服务凭证鉴权：内部接口仅接受 X-Service-Key 头，凭证只从环境变量读取。"""
from fastapi import Header, HTTPException, status

from .config import REVIEW_SERVICE_KEYS


def require_service_key(x_service_key: str = Header(..., alias="X-Service-Key")) -> str:
    if x_service_key not in REVIEW_SERVICE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing service credentials",
        )
    return x_service_key
