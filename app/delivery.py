"""outbox 投递任务：至少一次（at-least-once）推送 ai_draft_events 给订阅模块。

- 只把 delivered_at 为空的事件按 created_at 顺序投递；
- 订阅方 HTTP 2xx 才标记 delivered_at（至少一次语义：失败下次重试，订阅方按 draft_id 去重）；
- 订阅方对接说明见 README。

命令行：
    python -m app.delivery --once   # 投递一轮
    python -m app.delivery          # 常驻循环（--interval 秒）
"""
import argparse
import json
import logging
import time
import urllib.error
import urllib.request

from .config import DRAFT_EVENT_SUBSCRIBER_URL, DELIVERY_BATCH_SIZE
from .db import SessionLocal
from .models import DraftEvent, utcnow

logger = logging.getLogger("delivery")


def http_post_json(url: str, body: dict, timeout: int = 10) -> bool:
    """推送单个事件，2xx 返回 True。"""
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


def deliver_pending(session, poster=http_post_json, url: str | None = None,
                    batch_size: int = DELIVERY_BATCH_SIZE) -> int:
    """投递一轮未送达事件，返回本轮成功投递数。"""
    target_url = url or DRAFT_EVENT_SUBSCRIBER_URL
    if not target_url:
        logger.warning("DRAFT_EVENT_SUBSCRIBER_URL not configured, skip")
        return 0

    events = (
        session.query(DraftEvent)
        .filter(DraftEvent.delivered_at.is_(None))
        .order_by(DraftEvent.created_at)
        .limit(batch_size)
        .all()
    )
    delivered = 0
    for ev in events:
        ev.delivery_attempts = (ev.delivery_attempts or 0) + 1
        ok = poster(target_url, {
            "event_id": ev.id,
            "event_type": ev.event_type,
            "draft_id": ev.draft_id,
            "feature_code": ev.feature_code,
            "source_type": ev.source_type,
            "source_id": ev.source_id,
            "payload": ev.payload,
        })
        if ok:
            # 至少一次语义：仅 2xx 后标记已投递；失败保留，下轮重试
            ev.delivered_at = utcnow()
            delivered += 1
        session.commit()
    return delivered


def main() -> None:
    parser = argparse.ArgumentParser(description="ai_draft_events outbox delivery worker")
    parser.add_argument("--once", action="store_true", help="只投递一轮后退出")
    parser.add_argument("--interval", type=int, default=30, help="常驻模式轮询间隔秒数")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        session = SessionLocal()
        try:
            n = deliver_pending(session)
            if n:
                logger.info("delivered %d events", n)
        finally:
            session.close()
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
