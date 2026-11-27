"""真实 Locust 压测脚本（Locust 2.47.0）。

用法（先另开终端起桩服务）：
  DELAY_SCALE=1.0 python tools/stub_server.py --port 8901
  locust -f locustfile.py --headless -u 8 -r 2 -t 20s \
         --host http://127.0.0.1:8901 --csv=samples/locust/run
"""
from locust import HttpUser, constant_pacing, task


class MemberApiUser(HttpUser):
    wait_time = constant_pacing(0.0)

    @task(3)
    def members(self):
        self.client.get("/api/members")

    @task(3)
    def prospects(self):
        self.client.get("/api/prospects")

    @task(1)
    def orders_export(self):
        self.client.get("/api/orders/export")
