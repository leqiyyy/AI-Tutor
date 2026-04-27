# 前后端联调接口清单 V1

## 1. 目标

这份文档用于约定本项目第一版前后端联调范围，避免后端仅通过阅读前端页面而漏掉关键接口。

本版联调的核心目标：

- 支持 `学生 / 教师 / 管理员` 三类账号登录。
- 后端预置 3 个演示账号，各自拥有完整演示数据。
- 学生和教师注册时，不需要管理员审核通过。
- 用户必须先完成验证码校验，验证码通道支持 `邮箱` 或 `手机号`。
- 验证码校验成功后，账号立即注册成功，可直接登录。
- 管理员端可以查看注册记录，但不承担注册放行职责。
- 新注册的普通账号默认从 0 开始，不自动拥有演示课程、通知、作业或课程空间内容。

## 2. 优先级定义

- `P0`：必须优先完成，完成后主链路可以跑通。
- `P1`：强相关业务接口，建议第二阶段完成。
- `P2`：增强型功能接口，可在主链路稳定后补齐。

## 3. 全局约定

### 3.1 接口基准

- 基础前缀：`/api`
- 建议统一返回包裹格式：

```json
{
  "data": {},
  "message": "ok",
  "meta": {}
}
```

- 错误返回建议统一为：

```json
{
  "code": "INVALID_VERIFY_CODE",
  "message": "验证码无效或已过期",
  "errors": {
    "verifyCode": "验证码无效或已过期"
  }
}
```

### 3.2 数据格式约定

- 所有 `id` 建议统一使用字符串。
- 所有时间字段建议返回 ISO 8601 字符串，例如 `2026-04-11T08:30:00Z`。
- 列表为空时返回 `[]`，不要返回 `null`。
- 数值统计为空时返回 `0`。
- 分页接口建议在 `meta` 中返回 `page / pageSize / total`。

### 3.3 认证约定

- 登录成功后返回 `accessToken`，可选返回 `refreshToken`。
- 前端后续请求默认走 `Authorization: Bearer <token>`。
- 建议提供 `GET /api/auth/me`，用于页面刷新后恢复登录态。
- 注册成功后不要求自动登录，但用户应当可以立即去登录页使用新账号登录。
- 如果后端希望“注册成功即自动登录”，也可以在 `POST /api/auth/register` 中直接返回 token；如采用该方案，请提前通知前端。

### 3.4 权限约定

- 学生访问未加入的课程：返回 `403` 或 `404`。
- 教师访问不属于自己的课程：返回 `403`。
- 管理员接口仅管理员可访问：返回 `403`。

## 4. 演示账号与空账号规则

### 4.1 演示账号规则

后端应预置 3 个演示账号。账号名和密码可以后端自定，但必须在联调说明中明确提供。

建议至少包含：

- 演示学生账号：有课程、通知、待办、作业、问答、讨论、错题、学习卡组等数据。
- 演示教师账号：有课程、学生列表、课程资料、已发布任务、问答、讨论、通知等数据。
- 演示管理员账号：有系统概览、注册记录、用户列表、课程列表、举报/审核数据等数据。

### 4.2 新注册账号规则

- 新注册学生账号：
  - 完成验证码校验后立即可用。
  - 登录后首页默认空数据。
  - `courses=[]`、`notifications=[]`、统计值为 `0`。
  - 只有加入课程后才出现课程与课程空间数据。

- 新注册教师账号：
  - 完成验证码校验后立即可用。
  - 登录后首页默认空数据。
  - `courses=[]`、`notifications=[]`、统计值为 `0`。
  - 只有创建课程后才出现课程与班级数据。

- 管理员账号：
  - 不走开放注册。
  - 默认由系统预置或后台创建。

### 4.3 注册记录规则

- 所有学生/教师注册都应写入注册记录表。
- 管理员端可以查询注册记录。
- 注册记录用于审计、统计、回溯，不用于阻塞登录。

建议注册记录至少包含：

- `registrationId`
- `userId`
- `role`
- `realName`
- `account`
- `email`
- `phone`
- `verifyChannel`
- `verifiedAt`
- `registeredAt`
- `source`

### 4.4 关键业务原则

- 演示数据必须绑定在“具体演示账号”上，而不是绑定在“角色”上。
- 不能因为用户角色是学生，就默认返回演示学生数据。
- 不能因为用户角色是教师，就默认返回演示教师数据。

## 5. P0 接口清单

### 5.1 认证与注册

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P0 | `POST` | `/api/auth/login` | 登录 |
| P0 | `POST` | `/api/auth/send-verify-code` | 发送注册验证码 |
| P0 | `POST` | `/api/auth/register` | 学生/教师注册 |
| P0 | `GET` | `/api/auth/me` | 获取当前登录用户 |
| P0 | `POST` | `/api/auth/logout` | 登出，可选，前端也可仅清 token |

#### `POST /api/auth/login`

请求体：

```json
{
  "role": "student",
  "account": "demo_student",
  "password": "******"
}
```

响应体最低字段：

```json
{
  "data": {
    "accessToken": "token",
    "refreshToken": "refresh-token",
    "expiresAt": "2026-04-12T08:00:00Z",
    "redirectTo": "/student-dashboard",
    "user": {
      "id": "user_001",
      "role": "student",
      "name": "演示学生",
      "displayName": "演示学生",
      "account": "demo_student",
      "email": "demo_student@example.com"
    }
  }
}
```

#### `POST /api/auth/send-verify-code`

说明：

- 后端应支持邮箱和手机号两种验证码通道。
- 当前前端首版注册页优先走邮箱验证码，但接口请按通用方式设计，避免后续新增手机号验证时破坏兼容。

请求体：

```json
{
  "role": "teacher",
  "channel": "email",
  "target": "teacher@example.com"
}
```

或：

```json
{
  "role": "student",
  "channel": "phone",
  "target": "13800000000"
}
```

响应体最低字段：

```json
{
  "data": {
    "cooldownSeconds": 60,
    "delivery": "email",
    "maskedTarget": "te***@example.com"
  }
}
```

#### `POST /api/auth/register`

说明：

- 该接口同时承载学生和教师注册。
- 建议通过 `role` 区分不同字段。
- 当前规则是“验证码通过即注册成功”，不需要管理员审核。

学生请求体最低字段：

```json
{
  "role": "student",
  "realName": "张三",
  "studentId": "2024301001",
  "email": "student@example.com",
  "phone": "13800000000",
  "school": "某大学",
  "college": "计算机学院",
  "major": "软件工程",
  "grade": "2024级",
  "classNo": "1班",
  "password": "abc12345",
  "verifyCode": "123456"
}
```

教师请求体最低字段：

```json
{
  "role": "teacher",
  "realName": "李老师",
  "teacherId": "T2024001",
  "email": "teacher@example.com",
  "phone": "13900000000",
  "school": "某大学",
  "college": "计算机学院",
  "department": "软件工程系",
  "title": "讲师",
  "idCardNo": "420000199001011234",
  "certFile": "",
  "password": "abc12345",
  "verifyCode": "123456"
}
```

注册响应建议：

```json
{
  "data": {
    "status": "created",
    "message": "注册成功，可直接登录",
    "nextAction": "login"
  }
}
```

#### `GET /api/auth/me`

响应体最低字段与 `login.user` 保持一致。

### 5.2 学生主链路

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P0 | `GET` | `/api/student/dashboard` | 学生首页数据 |
| P0 | `POST` | `/api/student/courses/join-by-invite` | 学生通过邀请码加课 |
| P0 | `GET` | `/api/student/courses/:courseId` | 学生课程空间首屏数据 |

#### `GET /api/student/dashboard`

最低返回内容建议包含：

- `greetingName`
- `stats.activeCourses`
- `stats.pendingTasks`
- `stats.completionRate`
- `notifications[]`
- `courses[]`
- `todoItems[]`

新账号返回示例：

```json
{
  "data": {
    "greetingName": "新同学",
    "stats": {
      "activeCourses": 0,
      "pendingTasks": 0,
      "completionRate": 0
    },
    "notifications": [],
    "courses": [],
    "todoItems": []
  }
}
```

#### `POST /api/student/courses/join-by-invite`

请求体：

```json
{
  "inviteCode": "ABC123"
}
```

响应体建议包含：

- `courseId`
- `courseName`
- `teacherName`
- `joinedAt`

#### `GET /api/student/courses/:courseId`

这是学生课程页的首屏 bootstrap 接口，P0 最低返回建议包含：

- `course`
- `materialsSummary`
- `tasksSummary`
- `latestHomeworks`
- `latestDiscussions`

最低结构示例：

```json
{
  "data": {
    "course": {
      "id": "course_001",
      "name": "计算机网络",
      "teacher": "王教授",
      "code": "CS301"
    },
    "materialsSummary": [],
    "tasksSummary": [],
    "latestHomeworks": [],
    "latestDiscussions": []
  }
}
```

### 5.3 教师主链路

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P0 | `GET` | `/api/teacher/dashboard` | 教师首页数据 |
| P0 | `POST` | `/api/teacher/courses` | 教师创建课程 |
| P0 | `GET` | `/api/teacher/courses/:courseId` | 教师课程空间首屏数据 |

#### `GET /api/teacher/dashboard`

最低返回内容建议包含：

- `greetingName`
- `stats.activeCourses`
- `stats.totalStudents`
- `stats.pendingReviews`
- `notifications[]`
- `courses[]`

新教师账号返回规则：

- `courses=[]`
- `notifications=[]`
- 所有统计为 `0`

#### `POST /api/teacher/courses`

请求体最低字段：

```json
{
  "name": "计算机网络",
  "code": "CS301",
  "semester": "2026春",
  "description": "课程简介",
  "coverColor": "#3b82f6"
}
```

响应体建议包含：

- `courseId`
- `inviteCode`
- `createdAt`

说明：

- 学生加课链路依赖这里返回的邀请码。

#### `GET /api/teacher/courses/:courseId`

这是教师课程页的首屏 bootstrap 接口，P0 最低返回建议包含：

- `course`
- `stats`
- `recentFiles`
- `publishedTasks`
- `studentSummary`
- `pendingQuestions`

### 5.4 管理员主链路

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P0 | `GET` | `/api/admin/dashboard` | 管理员首页概览 |
| P0 | `GET` | `/api/admin/registrations` | 注册记录列表 |

#### `GET /api/admin/dashboard`

最低返回建议包含：

- 系统概览统计
- 注册趋势或注册总量
- 近期活动
- 基础系统状态

#### `GET /api/admin/registrations`

说明：

- 这是“注册记录查询”接口，不是“待审核列表”接口。
- 建议支持按 `role / channel / keyword / dateFrom / dateTo` 筛选。

最低字段建议包含：

- `registrationId`
- `userId`
- `role`
- `realName`
- `account`
- `email`
- `phone`
- `verifyChannel`
- `verifiedAt`
- `registeredAt`
- `source`

## 6. P1 接口清单

### 6.1 学生端

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P1 | `GET` | `/api/student/notifications` | 学生通知列表 |
| P1 | `POST` | `/api/student/notifications/read-all` | 全部标记已读 |
| P1 | `POST` | `/api/student/notifications/:id/read` | 单条标记已读 |
| P1 | `GET` | `/api/student/courses/:courseId/materials` | 课程资料列表 |
| P1 | `GET` | `/api/student/courses/:courseId/tasks` | 任务列表 |
| P1 | `POST` | `/api/student/courses/:courseId/tasks/:taskId/submissions` | 提交作业/考试 |
| P1 | `GET` | `/api/student/courses/:courseId/questions` | 我的提问列表 |
| P1 | `POST` | `/api/student/courses/:courseId/questions` | 新增提问 |
| P1 | `POST` | `/api/student/courses/:courseId/questions/:questionId/replies` | 提问追问/补充 |
| P1 | `GET` | `/api/student/courses/:courseId/discussions` | 讨论区列表 |
| P1 | `POST` | `/api/student/courses/:courseId/discussions` | 发布讨论 |
| P1 | `POST` | `/api/student/courses/:courseId/discussions/:discussionId/replies` | 回复讨论 |
| P1 | `POST` | `/api/student/courses/:courseId/teacher-help-requests` | AI 转人工请求 |

### 6.2 教师端

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P1 | `GET` | `/api/teacher/notifications` | 教师通知列表 |
| P1 | `POST` | `/api/teacher/notifications/read-all` | 教师通知全部已读 |
| P1 | `GET` | `/api/teacher/courses/:courseId/files` | 课程资料列表 |
| P1 | `POST` | `/api/teacher/courses/:courseId/files` | 上传资料 |
| P1 | `PATCH` | `/api/teacher/courses/:courseId/files/:fileId` | 重命名资料 |
| P1 | `DELETE` | `/api/teacher/courses/:courseId/files/:fileId` | 删除资料 |
| P1 | `GET` | `/api/teacher/courses/:courseId/tasks` | 已发布任务列表 |
| P1 | `POST` | `/api/teacher/courses/:courseId/notices` | 发布通知 |
| P1 | `POST` | `/api/teacher/courses/:courseId/homeworks` | 发布作业 |
| P1 | `POST` | `/api/teacher/courses/:courseId/exams` | 发布考试 |
| P1 | `GET` | `/api/teacher/courses/:courseId/questions` | 学生提问列表 |
| P1 | `POST` | `/api/teacher/courses/:courseId/questions/:questionId/replies` | 教师回复提问 |
| P1 | `GET` | `/api/teacher/courses/:courseId/students` | 学生列表 |
| P1 | `PATCH` | `/api/teacher/courses/:courseId/students/group` | 调整学生分组 |
| P1 | `GET` | `/api/teacher/courses/:courseId/discussions` | 讨论列表 |
| P1 | `POST` | `/api/teacher/courses/:courseId/discussions` | 发布讨论 |
| P1 | `POST` | `/api/teacher/courses/:courseId/discussions/:discussionId/replies` | 回复讨论 |

### 6.3 管理员端

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P1 | `GET` | `/api/admin/users` | 用户列表/搜索 |
| P1 | `PATCH` | `/api/admin/users/:userId/status` | 禁用/启用用户 |
| P1 | `POST` | `/api/admin/users/:userId/reset-password` | 重置密码 |
| P1 | `GET` | `/api/admin/courses` | 课程列表/搜索 |
| P1 | `PATCH` | `/api/admin/courses/:courseId/archive` | 课程归档 |
| P1 | `PATCH` | `/api/admin/courses/:courseId/owner` | 转移课程负责人 |

## 7. P2 接口清单

### 7.1 学生增强功能

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P2 | `GET` | `/api/student/courses/:courseId/mistakes` | 错题本 |
| P2 | `POST` | `/api/student/courses/:courseId/mistakes` | 新增错题 |
| P2 | `PATCH` | `/api/student/courses/:courseId/mistakes/:mistakeId/mastered` | 标记已掌握 |
| P2 | `GET` | `/api/student/courses/:courseId/decks` | 学习卡组列表 |
| P2 | `POST` | `/api/student/courses/:courseId/decks` | 创建卡组 |
| P2 | `POST` | `/api/student/courses/:courseId/decks/:deckId/review-records` | 记录复习结果 |

### 7.2 教师增强功能

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P2 | `POST` | `/api/teacher/courses/:courseId/exams/generate-questions` | AI 生成题目 |
| P2 | `POST` | `/api/teacher/courses/:courseId/files/:fileId/share` | 分享资料 |
| P2 | `POST` | `/api/teacher/courses/:courseId/exports` | 导出学生数据 |
| P2 | `GET` | `/api/teacher/ai-feedback` | AI 反馈聚合列表 |

### 7.3 管理员增强功能

| 优先级 | 方法 | 路径 | 作用 |
| --- | --- | --- | --- |
| P2 | `GET` | `/api/admin/reports` | 举报/审核列表 |
| P2 | `POST` | `/api/admin/reports/:reportId/resolve` | 处理举报 |
| P2 | `GET` | `/api/admin/announcements` | 系统公告列表 |
| P2 | `POST` | `/api/admin/announcements` | 发布系统公告 |
| P2 | `GET` | `/api/admin/backups` | 备份历史 |
| P2 | `POST` | `/api/admin/backups` | 立即备份 |
| P2 | `GET` | `/api/admin/settings` | 系统设置读取 |
| P2 | `PATCH` | `/api/admin/settings` | 系统设置更新 |

## 8. 种子数据建议

为了让前端演示页与当前视觉稿接近，建议种子数据至少达到以下规模：

### 8.1 演示学生账号

- 3 到 5 门课程
- 3 条以上通知
- 1 个待提交作业
- 1 个考试
- 1 条已批改记录
- 1 条提问
- 1 条讨论
- 1 组错题
- 1 组学习卡片

### 8.2 演示教师账号

- 3 到 6 门课程
- 每门课程至少 2 到 3 份资料
- 至少 1 条通知、1 个作业、1 个考试
- 至少 3 名学生
- 至少 1 条待回复提问
- 至少 1 条讨论

### 8.3 演示管理员账号

- 非零系统统计
- 至少 5 条注册记录
- 至少 5 条用户记录
- 至少 5 条课程记录
- 至少 2 条举报/审核记录

## 9. 建议的前后端联调顺序

1. 认证：登录、注册、验证码、`auth/me`
2. 首页：学生首页、教师首页、管理员首页
3. 主链路：教师创建课程、学生邀请码加课
4. 课程首屏：学生课程页、教师课程页 bootstrap
5. 列表与提交：资料、任务、通知、问答、讨论
6. 管理后台：注册记录、用户管理、课程管理
7. 增强能力：错题、卡组、导出、AI、系统设置

## 10. 前端联调入口文件

后端联调时，优先参考以下前端入口，而不是直接从超大页面组件里猜接口：

- 认证：`src/services/auth.ts`
- 首页：`src/services/dashboard.ts`
- 课程首屏：`src/services/course.ts`
- 运行时配置：`src/lib/env.ts`
- 通用请求：`src/lib/http.ts`
