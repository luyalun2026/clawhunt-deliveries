// k6 v2.4.0 压测脚本（会员空间平台 · 三接口混合读）
// 用法：k6 run --vus 8 --duration 20s --summary-export=samples/k6/summary.json \
//        --out json=samples/k6/result.jsonl tools/k6_script.js
import http from 'k6/http';

const BASE = __ENV.BASE || 'http://127.0.0.1:8901';

export const options = {
  vus: 8,
  duration: '20s',
};

export default function () {
  const eps = [
    ['/api/members', 3],
    ['/api/prospects', 3],
    ['/api/orders/export', 1],
  ];
  for (const [path, times] of eps) {
    for (let i = 0; i < times; i++) {
      http.get(BASE + path, { tags: { name: 'GET ' + path } });
    }
  }
}
