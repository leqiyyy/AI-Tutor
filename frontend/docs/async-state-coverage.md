# Async State Coverage

## Purpose

这份文档用于说明前端当前主要异步动作的 `loading / success / error` 覆盖情况，方便后端联调时定位问题。

---

## Coverage Rule

前端不要求每个按钮都有完全相同的 UI 样式，但每个重要异步动作至少满足：

- 发起请求时能禁用按钮、展示加载态或进入 pending 状态
- 成功后能刷新本地状态、关闭弹窗或展示成功反馈
- 失败后能展示错误信息、保留兜底数据或 alert 提示

---

## Covered Areas

### Auth

- 登录：`loading`、错误提示
- 注册：`loading`、字段错误、提交错误

### Dashboard

- 学生 Dashboard：读取错误、加入课程 pending、通知已读失败提示
- 教师 Dashboard：读取错误、创建课程 pending、通知已读失败提示
- 管理员 Dashboard：统一 `actionPending`、成功消息、错误提示

### Settings

- 学生设置：读取 loading、保存错误、头像上传错误、修改密码错误
- 教师设置：读取 loading、保存错误、头像上传错误、修改密码错误

### Student Course

- 课程 bootstrap：错误提示
- 首页/资料/任务/问答/讨论/FAQ：读取失败兜底为空数组
- 错题/闪卡/学习概览：service 读取失败兜底
- 作业提交、提问、讨论、闪卡复习：走 service，失败可由 service 抛错接入
- 零数据列表：已补空状态

### Teacher Course

- 课程 bootstrap：错误提示
- 课程首页、资料、任务、问答、学生、讨论：读取失败兜底为空数组
- 资料上传：上传中状态、进度条、按钮禁用
- 资料预览：加载态、错误提示、兜底预览结构
- 资料下载：下载中状态、失败提示
- 资料 AI 解析：加载态、错误提示、兜底解析结构
- 任务详情：加载态、错误提示、兜底详情结构
- AI 回答详情：加载态、错误提示、兜底回答结构
- 学生管理：空状态、除零保护

### Student AI Assistant

- 会话读取、消息读取、发送消息、点赞/点踩、反馈、转教师均通过 `aiService`
- 失败时保留本地兜底回复或错误反馈入口

### Teacher AI Assistant

- 会话读取、消息读取、发送消息均通过 `aiService`
- AI 问题队列、反馈队列、人工回复、采纳 AI、反馈处理均通过 `aiService`
- 工具区生成动作：加载态、结果区、错误提示
- 溯源区：优先通过 `aiService.getMessageSources()`，失败回落消息内 sources

---

## Remaining Refinement

后端真实联调时，可以继续增强：

- 更统一的 Toast 成功提示
- 按具体操作拆分 pending 状态，避免多个按钮共用一个 pending
- 对文件预览、下载和长任务生成增加轮询或任务状态接口

