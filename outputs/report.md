# S3-MINI-045 脱敏自动化测试 · 运行报告

- 生成时间：2026-11-23 22:45:23
- Python：3.13.14 / FastAPI + httpx TestClient

## 扫描规模（AC #1）
- OpenAPI 枚举到的 /api/mini/ GET 接口数：**9**
- 身份数：**4**（guest, none, member, admin）
- 接口 × 身份 × 路径填充 的请求总数：**88**
- 每个响应递归检查：金丝雀值（32 个）× 禁键 7 种 × 手机号/邮箱/座机正则

## 结果
- 主套件：**25 passed，0 failed**（outputs/pytest_main.txt）
- 负向套件：**2 个用例按预期失败**（outputs/pytest_negative_expected_fail.txt）

## 被扫描接口清单
- `/api/mini/companies`（路径参数 无，查询参数 无）
- `/api/mini/companies/{company_id}`（路径参数 ['company_id']，查询参数 无）
- `/api/mini/companies/{company_id}/contacts`（路径参数 ['company_id']，查询参数 无）
- `/api/mini/map/nearby`（路径参数 无，查询参数 ['lat', 'lng']）
- `/api/mini/map/streets`（路径参数 无，查询参数 无）
- `/api/mini/map/streets/{street_id}/points`（路径参数 ['street_id']，查询参数 无）
- `/api/mini/notices`（路径参数 无，查询参数 无）
- `/api/mini/notices/{notice_id}`（路径参数 ['notice_id']，查询参数 无）
- `/api/mini/profile`（路径参数 无，查询参数 无）

## 负向证据（AC #2 / AC #3）
破坏版应用（app/broken_app.py）注入 phone 禁键与高精度坐标，同一套断言必须拦截。
负向套件运行结果：2 个用例 FAILED（完整输出见 outputs/pytest_negative_expected_fail.txt）。

### 失败输出节选
```text
AssertionError: 联系方式脱敏校验失败，共 3 处违规：
E           $.phone: 禁键「phone」出现在响应中
E           $.phone: 金丝雀值泄露
E           $.phone: 字符串命中手机号正则

app\assertions.py:87: AssertionError
________________________ test_precise_coord_must_fail _________________________

    def test_precise_coord_must_fail():
        """AC #3：故意在地图点位中返回非街道中心点坐标后测试失败。"""
        r = client.get("/api/mini/map/streets/st-0101/points")
        assert r.status_co
----
AssertionError: 街道级坐标校验失败，共 4 处违规：
E           $[0]: 坐标 (30.5123451, 114.3123451) 不等于任何街道中心点
E           $[0]: 坐标小数位数 7 超过 4 位
E           $[1]: 坐标 (30.5123461, 114.3123461) 不等于任何街道中心点
E           $[1]: 坐标小数位数 7 超过 4 位

app\assertions.py:128: AssertionError
============================== warnings summary ===============================
..\..\..\..\.workbuddy\binaries\python\versions\3.13.12\Lib\site-packages\fastapi\testc
----
```

## 复现方式
```bash
pip install fastapi httpx pytest
python verify.py   # 一键复现：主套件必须全过，负向套件必须失败
pytest tests -v    # 仅跑主套件（CI 同款）
```