# 埋点事件字典（首批 13 个核心事件）

> 本文件由 track/generate.py 自动生成，请勿手工修改；
> 变更请修改 track/event_dictionary.yaml 并走数据管理员评审流程。

## app_launch

- 说明：小程序启动
- 触发时机：冷启动/热启动进入前台
- 所在页面：全局
- 自动采集：是
- 负责人：数据组-李工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| （无属性） | | | |

## page_view

- 说明：页面浏览
- 触发时机：页面 onShow
- 所在页面：全局
- 自动采集：是
- 负责人：数据组-李工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | string | 是 | 页面路径 |
| keyword | string | 否 | 搜索词（允许记录） |

## auth_success

- 说明：登录成功
- 触发时机：登录接口返回成功
- 所在页面：登录页
- 自动采集：是
- 负责人：数据组-王工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| method | string | 是 | 登录方式；取值 wechat/password |

## auth_apply

- 说明：提交入驻/认证申请
- 触发时机：申请表单提交
- 所在页面：认证申请页
- 自动采集：否
- 负责人：数据组-王工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| apply_kind | string | 是 | 申请类型；取值 member/vendor |

## resource_view

- 说明：资源详情浏览
- 触发时机：资源详情页 onShow
- 所在页面：资源详情页
- 自动采集：是
- 负责人：数据组-李工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| item_id | string | 是 | 资源 ID |
| from | string | 是 | 进入来源；取值 list/search/share/recommend |

## resource_publish

- 说明：资源发布
- 触发时机：发布成功回调
- 所在页面：资源发布页
- 自动采集：否
- 负责人：数据组-张工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| item_id | string | 是 | 资源 ID |
| kind | string | 是 | 供需类型；取值 supply/demand |

## connect_request

- 说明：提交对接申请
- 触发时机：对接申请提交成功
- 所在页面：资源详情页
- 自动采集：否
- 负责人：数据组-张工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| item_id | string | 是 | 资源 ID |

## event_view

- 说明：活动详情浏览
- 触发时机：活动详情页 onShow
- 所在页面：活动详情页
- 自动采集：是
- 负责人：数据组-李工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| event_id | string | 是 | 活动 ID |

## event_register

- 说明：活动报名
- 触发时机：报名表单提交成功
- 所在页面：活动详情页
- 自动采集：否
- 负责人：数据组-张工（虚构）
- 版本：1.1.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| event_id | string | 是 | 活动 ID |
| signup_state | string | 是 | 报名结果；取值 signed/waitlisted |

## event_checkin

- 说明：活动签到
- 触发时机：签到成功
- 所在页面：签到页
- 自动采集：否
- 负责人：数据组-张工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| event_id | string | 是 | 活动 ID |
| method | string | 是 | 签到方式；取值 qrcode/manual |

## faq_ask

- 说明：提问 FAQ / 知识库
- 触发时机：问题提交
- 所在页面：帮助页
- 自动采集：是
- 负责人：数据组-王工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| question_len | integer | 是 | 问题字符数（不记录原文） |
| hit_faq | boolean | 否 | 是否命中 FAQ |
| keyword | string | 否 | 搜索词（允许记录） |

## faq_feedback

- 说明：答案反馈
- 触发时机：点赞/点踩
- 所在页面：帮助页
- 自动采集：否
- 负责人：数据组-王工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| answer_id | string | 是 | 答案 ID |
| useful | boolean | 是 | 是否有帮助 |

## share

- 说明：分享
- 触发时机：转发成功回调
- 所在页面：全局
- 自动采集：是
- 负责人：数据组-李工（虚构）
- 版本：1.0.0　状态：active

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | string | 是 | 被分享页面 |
| target_type | string | 是 | 分享对象类型；取值 resource/event/article/mini_program |
| target_id | string | 否 | 对象 ID（页面级分享为空） |
