"""集中读取环境变量，禁止在代码中硬编码配置与密钥。"""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ch2154.db")

# 服务凭证（内部接口鉴权），逗号分隔，例如 REVIEW_SERVICE_KEYS=svc-crm-xxx,svc-kb-xxx
REVIEW_SERVICE_KEYS = set(
    k for k in os.getenv("REVIEW_SERVICE_KEYS", "svc-test-key").split(",") if k
)

# 事件投递任务推送的订阅方 webhook 地址
DRAFT_EVENT_SUBSCRIBER_URL = os.getenv("DRAFT_EVENT_SUBSCRIBER_URL", "")

# 投递任务单轮最大事件数
DELIVERY_BATCH_SIZE = int(os.getenv("DELIVERY_BATCH_SIZE", "100"))
