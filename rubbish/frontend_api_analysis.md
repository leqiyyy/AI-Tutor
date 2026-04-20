# 前端 API 依赖分析报告

## 1. 结论摘要

本项目当前前端是一个 **React + TypeScript + Vite 的高保真原型**，页面层级与业务意图已经比较完整，但真正落地到后端的接口很少，绝大多数页面仍然使用本地 `useState`、静态数组、`console.log` 和 `localStorage` 模拟业务。

因此，后端设计不能简单理解为“把现有前端已经调用的接口补齐”，而应分成两类约束：

1. **硬约束**  
   来自页面结构、页面命名、路由层级、表单字段、局部数据形状、查询参数形状。
2. **软约束**  
   来自页面中的 TODO 注释、`console.log('...API调用')`、本地模拟数据，这些代表“前端预期要有这些能力”，但并不是已经固定好的最终契约。

此外，现有两份文档旧版本存在编码乱码，本次已重写为 UTF-8 文本。

---

## 2. 前端项目结构与技术事实

### 2.1 项目结构

- 前端目录：`frontend/`
- 路由配置：`frontend/src/router/config.tsx`
- 页面目录：`frontend/src/pages/`
- 课程级 AI 组件：
  - `frontend/src/pages/student-course/components/AIAssistant.tsx`
  - `frontend/src/pages/teacher-course/components/TeacherAIAssistant.tsx`

### 2.2 技术栈

- React 19
- TypeScript
- Vite
- React Router
- Tailwind CSS

### 2.3 请求层现状

- **没有统一 API Client**
- **没有 axios/request 封装**
- **没有统一 baseURL 配置**
- **没有前端鉴权拦截器**
- **没有 token 存储实现**
- 当前唯一真实 `fetch` 调用在注册页，且提交到外部 `readdy.ai` 表单地址，不是项目后端

### 2.4 环境变量现状

前端未发现与业务后端相关的 `VITE_API_BASE_URL` 或 `import.meta.env` 请求配置。`vite.config.ts` 中只有 Readdy 相关构建变量。

这意味着当前联调约束主要来自：

- 固定路径 `/api/...` 的 TODO 注释
- 页面跳转参数
- 页面组件内部的数据结构

---

## 3. 前端页面与路由树

前端当前只有 8 个一级路由，复杂功能主要通过页面内 tab/section 切换实现。

| 路由 | 页面 | 角色 |
|---|---|---|
| `/` | Login | 公共 |
| `/login` | Login | 公共 |
| `/register` | Register | 公共 |
| `/teacher-dashboard` | TeacherDashboard | 教师 |
| `/student-dashboard` | StudentDashboard | 学生 |
| `/admin-dashboard` | AdminDashboard | 管理员 |
| `/teacher-course/:id` | TeacherCourse | 教师 |
| `/student-course/:id` | StudentCourse | 学生 |

### 3.1 与目标业务树的映射情况

前端已经覆盖了你要求的大部分导航树，但实现方式是“单页面多分区”，不是多级路由：

- 教师端：
  - 工作台
  - 我的课程
  - 通知中心
  - 个人设置
  - 课程内进一步包含：班级首页、课程知识、任务中心、互动空间、学生管理、AI助教
- 学生端：
  - 学习空间
  - 我的课程
  - 通知中心
  - 个人中心
  - 课程内进一步包含：班级首页、课程资料、任务中心、互动空间、AI助教、学习闪卡、学习数据
- 管理端：
  - 系统概览
  - 用户管理
  - 课程管理
  - 内容审核
  - 系统设置

结论：**后端模块划分必须映射到这棵业务树，但 API 可以按资源路由设计，不必照搬页面内 tab 名称。**

---

## 4. 前端请求与鉴权分析

### 4.1 鉴权与 token 存储

当前前端：

- 登录页仅做本地校验后跳转
- 没有调用后端登录接口
- 没有 `Authorization` 头处理
- 没有 token 刷新机制
- 没有用户态持久化

当前唯一 `localStorage` 业务键：

- `luoying_ai_feedback`

用途：

- 学生端 AI 助教点踩后写入本地
- 教师端 AI 助教审核队列从本地轮询读取

### 4.2 请求封装缺失带来的后端兼容策略

由于前端没有统一请求封装，后端联调阶段建议默认采用：

- 路由前缀：`/api/v1`
- 统一响应包裹：`{ code, message, data }`
- CORS 直接放开前端本地地址

后续前端若新增请求封装，可再统一 header、分页、错误码、token 续期。

---

## 5. 已明确的接口事实

这里分为三类：

1. **显式 TODO**：代码里明确写了某个接口
2. **显式 API 调用占位**：代码里通过 `console.log('...API调用')` 标示
3. **隐式契约**：虽然没写接口，但页面形状已经固定了后端至少要返回什么数据

### 5.1 显式 TODO

| 来源文件 | 接口 | 说明 |
|---|---|---|
| `frontend/src/pages/register/page.tsx` | `POST /api/auth/send-verify-code` | 发送验证码 |
| `frontend/src/pages/register/page.tsx` | `POST /api/auth/register` | 用户注册 |

### 5.2 登录接口的真实前端约束

登录页虽然没有 TODO，但表单结构已经明确：

```ts
{
  account: string
  password: string
  role: 'student' | 'teacher' | 'admin'
}
```

注意点：

- UI 文案是“学号/邮箱”“工号/邮箱”“管理员账号”
- 也就是说前端当前收集的是 **`account`**，不是固定 `email`
- 现有后端实现却是 `email + password + role`

结论：

- 为了兼容前端，后端后续应支持 `account` 登录，内部可同时匹配 `email / student_id / teacher_id`
- 如果坚持只收 `email`，则未来必须改前端登录页，这不符合当前“后端优先兼容前端”的要求

### 5.3 注册接口字段事实

注册页当前表单字段使用 **camelCase**，并区分学生/教师：

学生注册字段：

```json
{
  "role": "student",
  "realName": "string",
  "studentId": "string",
  "email": "string",
  "phone": "string",
  "school": "string",
  "college": "string",
  "major": "string",
  "grade": "string",
  "classNo": "string",
  "password": "string",
  "confirmPassword": "string",
  "verifyCode": "string"
}
```

教师注册字段：

```json
{
  "role": "teacher",
  "realName": "string",
  "teacherId": "string",
  "email": "string",
  "phone": "string",
  "school": "string",
  "college": "string",
  "department": "string",
  "title": "string",
  "idCardNo": "string",
  "certFile": "string",
  "password": "string",
  "confirmPassword": "string",
  "verifyCode": "string"
}
```

现有后端 `backend/app/schemas/auth.py` 使用的是 `snake_case`：

- `real_name`
- `student_id`
- `teacher_id`
- `class_no`
- `confirm_password`
- `verify_code`

结论：

- 当前后端注册 schema **与前端不兼容**
- MVP 阶段应优先通过 Pydantic alias 或双格式兼容方式支持 camelCase 请求

---

## 6. 前端各页面的数据依赖

## 6.1 登录页 `Login`

核心数据：

- 登录角色
- 账号
- 密码

后端最低需要：

- 登录接口
- 当前用户接口
- 角色信息

建议接口：

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

---

## 6.2 注册页 `Register`

核心数据：

- 学生/教师差异化注册表单
- 邮箱验证码
- 注册申请结果

后端最低需要：

- 发送验证码
- 注册
- 审核状态字段预留

建议接口：

- `POST /api/v1/auth/send-verify-code`
- `POST /api/v1/auth/register`

补充说明：

- 前端当前还保留“管理员审核通过后再登录”的产品语义
- 因此后端用户表最好预留 `approval_status`
- 当前现有后端 `User` 模型没有该字段

---

## 6.3 教师工作台 `TeacherDashboard`

页面数据依赖：

- 今日教学概览
- 日历/课程安排
- 最近动态
- 教师课程卡片列表
- 通知列表
- 个人资料与密码修改

当前页面内的后端意图：

- 保存个人资料
- 修改密码
- 创建课程/班级
- 获取课程列表
- 获取通知列表

建议接口：

- `GET /api/v1/courses`
- `POST /api/v1/courses`
- `GET /api/v1/notifications`
- `GET /api/v1/courses/{course_id}/analytics`
- `GET /api/v1/auth/me`
- `PUT /api/v1/users/me`

---

## 6.4 教师课程页 `TeacherCourse`

这是教师端最关键的业务页，承担了课程知识库闭环的大部分前端入口。

### 6.4.1 班级首页 / 公告 / 最近任务 / 最近资料

依赖数据：

- 班级基本信息
- 公告
- 最近任务
- 最近资料
- 学情摘要

建议接口：

- `GET /api/v1/classes/{id}`
- `GET /api/v1/courses/{course_id}/files`
- `GET /api/v1/tasks`
- `GET /api/v1/courses/{course_id}/analytics`

### 6.4.2 课程知识

依赖数据：

- 资料列表
- 上传进度与解析状态
- 知识库状态
- 知识图谱节点/关系

页面中已明确预留的后端动作：

- 上传资料
- 获取文件列表
- 查看 AI 解析结果
- 查看知识图谱

建议接口：

- `POST /api/v1/courses/{course_id}/files/upload`
- `GET /api/v1/courses/{course_id}/files`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/courses/{course_id}/kb/status`
- `POST /api/v1/courses/{course_id}/kb/rebuild`
- `GET /api/v1/courses/{course_id}/graph`

### 6.4.3 任务中心

页面中已明确预留的后端动作：

- 发布通知
- 创建作业
- 创建考试
- 获取任务详情
- 更新任务状态

建议接口：

- `GET /api/v1/tasks`
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/notifications`
- `POST /api/v1/tasks/{task_id}/submit`
- `GET /api/v1/tasks/{task_id}/submissions`

### 6.4.4 互动空间

页面中已明确预留的后端动作：

- 讨论列表
- 发布讨论
- 回复讨论
- 点赞讨论
- 置顶讨论

建议接口：

- `GET /api/v1/classes/{id}/interactions`
- `POST /api/v1/classes/{id}/interactions`
- `POST /api/v1/classes/{id}/interactions/{interaction_id}/reply`
- `POST /api/v1/classes/{id}/interactions/{interaction_id}/like`
- `POST /api/v1/classes/{id}/interactions/{interaction_id}/pin`

### 6.4.5 学生管理

依赖数据：

- 学生列表
- 学生分组
- 进度、作业、出勤、预警
- 数据导出

建议接口：

- `GET /api/v1/classes/{id}/members`
- `POST /api/v1/classes/{id}/invite`
- `GET /api/v1/courses/{course_id}/analytics`
- `GET /api/v1/students/{student_id}/profile`

### 6.4.6 教师 AI 助教

依赖数据：

- 会话列表
- 消息列表
- AI 回答
- 文件附件
- citations
- 教学建议
- 学情问答
- 审核队列

教师 AI 组件当前事实：

- 支持会话列表与历史消息
- 支持上传文件上下文
- 支持根据课程数据生成备课/学情建议
- 审核队列当前从 `localStorage('luoying_ai_feedback')` 读取

建议接口：

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/query-with-image`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}/messages`
- `GET /api/v1/reviews/pending`
- `POST /api/v1/reviews/{review_id}/submit`

---

## 6.5 学生工作台 `StudentDashboard`

页面数据依赖：

- 待办任务
- 学习建议
- 课程进度
- 课程卡片
- 通知中心
- 个人中心概览

页面行为中已经固定的跳转参数：

- `?section=tasks&taskId=...&taskType=...`
- `?section=materials&chapterId=...`

结论：

- 后端在任务、资料接口中必须返回稳定的 `task_id`、`chapter_id`
- 否则学生工作台跳转无法精确高亮目标项

---

## 6.6 学生课程页 `StudentCourse`

这是学生端最复杂页面，几乎覆盖了你定义的所有学生业务。

### 6.6.1 班级首页

依赖数据：

- 课程基本信息
- 最近公告
- 课程问答入口
- 学习建议

### 6.6.2 课程资料

页面已显式预留动作：

- 获取文件预览
- 下载文件
- 查看 AI 解析结果
- 查看知识图谱
- 全文搜索

建议接口：

- `GET /api/v1/courses/{course_id}/files`
- `GET /api/v1/courses/{course_id}/files/{file_id}/preview`
- `GET /api/v1/courses/{course_id}/files/{file_id}/download`
- `GET /api/v1/courses/{course_id}/files/{file_id}/analysis`
- `GET /api/v1/courses/{course_id}/graph`
- `GET /api/v1/courses/{course_id}/search`

### 6.6.3 任务中心

页面已显式预留动作：

- 获取作业详情
- 提交作业
- 获取批改结果

建议接口：

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/submit`
- `GET /api/v1/tasks/{task_id}/submissions`

### 6.6.4 错题/学习增强

页面已显式预留动作：

- 开始练习错题
- 更新错题状态
- 添加错题

这部分不在你给的硬性 API 清单里，但前端已有明确预期。建议作为 MVP 后增强能力，或并入 `student_profiles / flashcards / analytics`。

### 6.6.5 互动空间

页面已显式预留动作：

- 提交问题回复
- 添加新提问
- 提交讨论回复
- 点赞讨论
- 发布新讨论
- AI 转人工申请

建议接口：

- `GET /api/v1/classes/{id}/interactions`
- `POST /api/v1/classes/{id}/interactions`
- `POST /api/v1/classes/{id}/questions`
- `POST /api/v1/classes/{id}/questions/{question_id}/reply`
- `POST /api/v1/reviews/escalate`

### 6.6.6 学生 AI 助教

学生 AI 组件当前已经固定的数据结构：

```ts
interface Message {
  id: number
  role: 'user' | 'ai'
  content: string
  time: string
  attachments?: AttachedFile[]
  sources?: { name: string; page: number; type: string }[]
  feedback?: 'like' | 'dislike'
  isWelcome?: boolean
}
```

```ts
interface Conversation {
  id: number
  title: string
  createdAt: string
  lastMessage: string
  messages: Message[]
}
```

这意味着后端至少要提供：

- 会话列表
- 消息列表
- AI 回答
- 溯源 sources
- 点赞/点踩反馈
- 多轮上下文
- 附件上下文
- 推荐追问/推荐资源

建议接口：

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/query-with-image`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}/messages`
- `POST /api/v1/chat/messages/{message_id}/feedback`

### 6.6.7 学习闪卡

页面已显式预留动作：

- 获取今日复习卡片
- 开始学习卡组
- 提交卡片回答
- 创建卡组

建议接口：

- `GET /api/v1/flashcards`
- `POST /api/v1/flashcards/{flashcard_id}/review`

### 6.6.8 学习数据/周报月报

页面已显式预留动作：

- 生成周报
- 生成月报
- 导出数据

建议接口：

- `GET /api/v1/students/me/profile`
- `GET /api/v1/courses/{course_id}/analytics`
- `GET /api/v1/students/me/reports/weekly`
- `GET /api/v1/students/me/reports/monthly`

其中周报/月报不在 MVP 强制清单，可作为增强功能。

---

## 6.7 管理端 `AdminDashboard`

页面数据依赖：

- 系统概览统计
- 用户审核与用户管理
- 课程管理
- 内容审核
- 系统设置

建议接口：

- `GET /api/v1/admin/overview`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/courses`
- `GET /api/v1/admin/reviews`
- `GET /api/v1/admin/model-config`
- `PUT /api/v1/admin/model-config`

---

## 7. 前端当前使用/预期的接口清单

以下清单按“前端强相关程度”划分。

### 7.1 已明确的核心接口

| 接口 | 来源 |
|---|---|
| `POST /api/v1/auth/login` | 登录页表单行为推导 |
| `POST /api/v1/auth/send-verify-code` | 注册页 TODO |
| `POST /api/v1/auth/register` | 注册页 TODO |
| `GET /api/v1/auth/me` | 登录后用户态所必需 |
| `GET /api/v1/courses` | 教师/学生课程卡片页 |
| `GET /api/v1/classes/{id}` | 课程首页 |
| `POST /api/v1/courses/{course_id}/files/upload` | 教师课程资料上传 |
| `GET /api/v1/courses/{course_id}/files` | 教师/学生资料页 |
| `POST /api/v1/chat/query` | 师生 AI 问答 |
| `GET /api/v1/chat/sessions` | 师生 AI 会话列表 |
| `GET /api/v1/chat/sessions/{session_id}/messages` | 师生 AI 消息历史 |
| `POST /api/v1/chat/messages/{message_id}/feedback` | 学生点赞/点踩 |
| `GET /api/v1/reviews/pending` | 教师审核队列 |
| `POST /api/v1/reviews/{review_id}/submit` | 教师补答与回流 |
| `GET /api/v1/flashcards` | 学生闪卡 |
| `POST /api/v1/flashcards/{flashcard_id}/review` | 闪卡复习结果 |
| `GET /api/v1/courses/{course_id}/analytics` | 教师/学生学情看板 |
| `GET /api/v1/students/me/profile` | 学生画像 |
| `GET /api/v1/admin/overview` | 管理端概览 |
| `GET /api/v1/admin/users` | 管理端用户管理 |

### 7.2 前端强烈暗示但尚未标准化的接口

| 能力 | 页面来源 |
|---|---|
| 课程搜索/全文检索 | 学生课程资料页 |
| 文件预览/下载/AI解析 | 学生课程资料页 |
| 知识图谱查看 | 师生课程页 |
| 讨论区 CRUD | 师生课程页 |
| 公告/作业/考试发布 | 教师课程页 |
| 作业提交与批改结果 | 学生课程页 |
| 错题本与掌握状态 | 学生课程页 |
| AI 转人工申请 | 学生课程页 |
| 周报/月报/导出 | 学生课程页 |

---

## 8. API 返回格式兼容要求

虽然前端当前没有真正消费项目后端，但从现有后端骨架和联调可控性考虑，推荐统一采用：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

分页推荐：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
}
```

### 8.1 需要特别兼容的字段形状

#### AI 消息 sources

前端当前使用：

```json
[
  { "name": "文件名", "page": 12, "type": "pdf" }
]
```

后端可增强为：

```json
[
  {
    "name": "文件名",
    "page": 12,
    "type": "pdf",
    "score": 0.91,
    "chunk_id": "chunk_xxx"
  }
]
```

前端至少要能兼容前三个字段。

#### 会话与消息 ID

前端当前类型写成 `number`，但后端更适合用字符串 UUID。  
建议联调阶段返回字符串 ID，并在后续前端联调时把前端类型放宽到 `string | number`。如果坚持零前端改动，则需要种子数据与测试环境暂时返回数字风格 ID。

#### 课程与班级 ID

当前前端 mock 跳转使用 `/teacher-course/1`、`/student-course/1`。  
若后端要做到“尽量不改前端”，推荐在种子数据中提供稳定、可预测的演示课程/班级 ID，至少保证开发联调路径可直达。

---

## 9. 前端与现有后端代码的冲突点

扫描发现以下关键不兼容项：

### 9.1 路由命名不兼容

现有后端主要使用：

- `/api/v1/classes/...`
- `/api/v1/chat/send`
- `/api/v1/analytics/class/...`

而本项目目标清单要求的核心路由是：

- `/api/v1/courses`
- `/api/v1/chat/query`
- `/api/v1/courses/{course_id}/analytics`
- `/api/v1/reviews/pending`

结论：**现有后端路由需要重组。**

### 9.2 注册字段命名不兼容

- 前端：camelCase
- 现有后端：snake_case

### 9.3 登录字段语义不兼容

- 前端：`account`
- 现有后端：`email`

### 9.4 AI 审核流仍停留在 localStorage

- 学生点踩写本地
- 教师审核读本地
- 尚未迁移到数据库与后端接口

### 9.5 无统一 token 流程

当前前端还没有：

- 保存 token
- 自动携带 Bearer token
- 401 处理

后端可以先完成标准 JWT，前端联调时再补薄适配层。

---

## 10. 缺失接口与优先级建议

### 10.1 MVP 必做

- 认证：登录、注册、当前用户
- 课程/班级：课程列表、班级详情、创建课程、创建班级、邀请码加入
- 文件与知识库：上传、文件列表、任务状态、知识库状态、知识图谱
- AI 助教：会话、提问、消息、反馈、追问建议、citation
- 审核：待审核列表、教师补答提交
- 闪卡：列表、复习结果提交
- 学情：课程概览、学生画像
- 通知：列表、已读
- 管理端：系统概览、用户列表、模型配置

### 10.2 可后置但应预留

- 错题本
- 周报/月报
- 资料 AI 解析详情页
- 更细粒度互动空间
- 多模态图片题目问答
- 学生导出

---

## 11. 对后端设计的直接约束

综合前端现状，后端在 Phase 1~3 应遵守以下兼容策略：

1. 登录接口优先兼容 `account + password + role`
2. 注册接口优先兼容 camelCase 字段
3. 统一返回 `{ code, message, data }`
4. 课程页路由参数允许字符串 ID，但种子数据尽量提供稳定演示 ID
5. AI 消息返回中必须至少包含：
   - `content`
   - `sources`
   - `confidence`
   - `suggestions`
   - `needs_review`
6. 教师审核队列的数据结构需要能覆盖当前 `luoying_ai_feedback` 的字段
7. 后端模块必须能映射教师端、学生端、管理端边界，不要把 AI 审核、知识图谱、闪卡、学情分析并成普通 LMS 接口

---

## 12. 最终判断

当前前端并没有“已经固化的大量 API 契约”，但已经把 **系统边界、核心闭环、关键数据形状、页面层级** 定死了。

后端实施时应优先满足三件事：

1. 对齐页面树和核心闭环，而不是只补静态 mock。
2. 优先兼容前端现有表单字段与局部数据形状，特别是登录/注册/AI消息/反馈。
3. 用标准化后端资源路由承接前端页面需求，并在文档中明确“哪些是前端已写死，哪些是后端新增设计”。
