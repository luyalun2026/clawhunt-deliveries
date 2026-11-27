// 自动生成：track/generate.py —— 请勿手工修改
// 会员空间平台埋点事件 SDK 类型定义（首批 13 个核心事件）

export interface AppLaunchProps {
}

export interface PageViewProps {
  /** 页面路径 */
  page: string;
  /** 搜索词（允许记录） */
  keyword?: string;
}

export interface AuthSuccessProps {
  /** 登录方式 */
  method: "wechat" | "password";
}

export interface AuthApplyProps {
  /** 申请类型 */
  apply_kind: "member" | "vendor";
}

export interface ResourceViewProps {
  /** 资源 ID */
  item_id: string;
  /** 进入来源 */
  from: "list" | "search" | "share" | "recommend";
}

export interface ResourcePublishProps {
  /** 资源 ID */
  item_id: string;
  /** 供需类型 */
  kind: "supply" | "demand";
}

export interface ConnectRequestProps {
  /** 资源 ID */
  item_id: string;
}

export interface EventViewProps {
  /** 活动 ID */
  event_id: string;
}

export interface EventRegisterProps {
  /** 活动 ID */
  event_id: string;
  /** 报名结果 */
  signup_state: "signed" | "waitlisted";
}

export interface EventCheckinProps {
  /** 活动 ID */
  event_id: string;
  /** 签到方式 */
  method: "qrcode" | "manual";
}

export interface FaqAskProps {
  /** 问题字符数（不记录原文） */
  question_len: number;
  /** 是否命中 FAQ */
  hit_faq?: boolean;
  /** 搜索词（允许记录） */
  keyword?: string;
}

export interface FaqFeedbackProps {
  /** 答案 ID */
  answer_id: string;
  /** 是否有帮助 */
  useful: boolean;
}

export interface ShareProps {
  /** 被分享页面 */
  page: string;
  /** 分享对象类型 */
  target_type: "resource" | "event" | "article" | "mini_program";
  /** 对象 ID（页面级分享为空） */
  target_id?: string;
}
