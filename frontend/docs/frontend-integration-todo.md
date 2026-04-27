# Frontend Integration ToDo

## Goal

将当前前端整理到以下状态：

- 所有主要页面都有明确的功能-接口映射
- 演示数据从页面组件中迁出，集中到 `mocks/*`
- 页面层只负责：`loading / empty / error / render / local ui state`
- 所有功能按钮和交互都保留，并为后端联调预留读写接口
- 支持后续 `demo 账号` 与 `普通账号` 共存

## Scope

本清单覆盖以下模块：

- 学生 Dashboard
- 教师 Dashboard
- 管理员 Dashboard
- 学生课程页
- 教师课程页
- 学生 AI 助教
- 教师 AI 助教

## Rules

1. 不删除现有功能按钮，只做分层整理
2. 组件内的“演示数据”不直接删除，而是迁移到 `mocks/*`
3. 所有未来会落地的交互必须归类为：
   - `Local UI only`
   - `Read API`
   - `Write API`
   - `Async workflow`
4. 前端不直接判断“显示假数据还是真数据”，而是统一由后端根据账号身份返回
5. 所有接口尽量保持统一返回结构，前端页面不直接写 `fetch`

---

## Global ToDo

### Phase 1 数据资产化

- [x] 将 Dashboard 页面中的演示数据迁移到 `src/mocks/dashboard.ts`
- [x] 新增 `src/mocks/admin-dashboard.ts`
- [x] 将课程页中的演示数据拆分迁移到 `src/mocks/course.ts`
- [x] 新增 `src/mocks/ai.ts`
- [x] 新增 `src/mocks/settings.ts`
- [x] 为每份 mock 数据标注：用途、页面来源、未来接口归属

### Phase 2 类型层补齐

- [x] 扩展 `src/types/dashboard.ts`
- [x] 扩展 `src/types/course.ts`
- [x] 新增 `src/types/ai.ts`
- [x] 新增 `src/types/settings.ts`
- [x] 新增管理员 Dashboard 类型

### Phase 3 服务层补齐

- [x] 扩展 `src/services/dashboard.ts`
- [x] 扩展 `src/services/course.ts`
- [x] 新增 `src/services/ai.ts`
- [x] 新增 `src/services/settings.ts`
- [x] 可选新增 `src/services/notifications.ts`

### Phase 4 认证与会话完善

- [x] 启动时调用 `authService.getCurrentUser()`
- [x] 增加路由守卫
- [x] 所有退出登录按钮统一走 `authService.logout()`
- [x] 用户会话模型补充 `isDemo`

### Phase 5 空状态与联调态完善

- [x] 为零数据账号补齐空状态
- [x] 为所有异步动作补齐 `loading / success / error`
- [x] 输出接口清单与联调文档

---

## Feature / API Matrix

## 1. 学生 Dashboard

### 文件

- `src/pages/student-dashboard/page.tsx`
- `src/pages/student-dashboard/components/StudentSettings.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 顶部 tab 切换 | `learning / courses / notifications / profile` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 用户菜单展开/收起 | 打开菜单、关闭菜单 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 退出登录 | 点击退出 | Write API | `authService.logout()` | 仅跳转登录页 | 改为清 session + 跳转 |
| 学习空间概览数据 | 统计卡片、课程、提醒 | Read API | `dashboardService.getStudentDashboard()` | 页面内硬编码 | 改为 service 驱动 |
| 快捷跳转作业 | 跳指定课程作业 | Local UI only | 无 | 已实现 | 保持本地，依赖课程页 query 参数 |
| 快捷跳转考试 | 跳指定课程考试 | Local UI only | 无 | 已实现 | 保持本地 |
| 快捷跳转资料 | 跳指定课程章节 | Local UI only | 无 | 已实现 | 保持本地 |
| 我的课程列表 | 课程卡片、进度、未读数 | Read API | `dashboardService.getStudentDashboard()` 或 `courseService.getStudentCourses()` | 页面内硬编码 | 后续抽离课程列表数据 |
| 加入课程弹窗 | 打开/关闭弹窗 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 加入课程提交 | 输入邀请码、提交加入 | Write API | `courseService.joinCourse(inviteCode)` | 仅 `alert` 演示 | 改为真实写接口 |
| 通知列表读取 | 通知内容、未读状态 | Read API | `notificationService.getStudentNotifications()` 或 dashboard 聚合接口 | 页面内硬编码 | 改为 service 驱动 |
| 通知筛选 | `all / task / teacher / ai` | Local UI only + Read API | 本地筛选或服务端筛选 | 本地筛选硬编码数据 | 先本地筛选接口结果，后续可服务端化 |
| 全部已读 | 一键已读 | Write API | `notificationService.markAllAsRead()` | 仅本地 state | 改为写接口 |
| 单条已读 | 点击单条通知 | Write API | `notificationService.markAsRead(id)` | 仅本地 state | 改为写接口 |
| 个人设置读取 | 基本信息、安全、通知、隐私、学习偏好 | Read API | `settingsService.getStudentSettings()` | 组件内本地默认值 | 改为读接口 |
| 个人设置保存 | 保存各分区设置 | Write API | `settingsService.updateStudentSettings()` | 组件内本地提交演示 | 改为写接口 |

### 待办

- [x] 抽取学生 Dashboard 演示数据到 `mocks/dashboard.ts`
- [x] 扩展 `StudentDashboardData`
- [x] 增加 `join course` 写接口
- [x] 增加学生通知服务
- [x] 增加学生设置服务
- [x] 页面改为 `dashboardService + settingsService` 驱动

---

## 2. 教师 Dashboard

### 文件

- `src/pages/teacher-dashboard/page.tsx`
- `src/pages/teacher-dashboard/components/TeacherSettings.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 顶部 tab 切换 | `overview / courses / notifications / settings` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 用户菜单展开/收起 | 打开菜单、关闭菜单 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 退出登录 | 点击退出 | Write API | `authService.logout()` | 仅跳转登录页 | 改为真实退出 |
| 工作台概览数据 | 统计卡片、课程、动态、日历 | Read API | `dashboardService.getTeacherDashboard()` | 页面内硬编码 | 改为 service 驱动 |
| 日历视图切换 | `week / month` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 日历月份切换 | 上一月/下一月 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 创建课程弹窗 | 打开/关闭 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 创建课程步骤流 | Step 1 -> Step 2 | Async workflow | `courseService.createCourse()` + `courseService.generateInviteCode()` | 本地演示 | 改为真实工作流 |
| 复制邀请码 | 复制到剪贴板 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 课程列表读取 | 我的课程列表 | Read API | `dashboardService.getTeacherDashboard()` 或 `courseService.getTeacherCourses()` | 页面内硬编码 | 改为 service 驱动 |
| 通知读取 | 教师通知流 | Read API | `notificationService.getTeacherNotifications()` | 页面内硬编码 | 改为 service 驱动 |
| 通知筛选 | `all / student / ai / task` | Local UI only + Read API | 可先本地筛选 | 本地 state | 后续按接口结果筛选 |
| 全部已读 | 批量已读 | Write API | `notificationService.markAllAsRead()` | 本地 state | 改为写接口 |
| 教师设置读取 | 个人资料、通知偏好、AI 配置 | Read API | `settingsService.getTeacherSettings()` | 组件内默认值 | 改为读接口 |
| 教师设置保存 | 保存资料/AI 配置 | Write API | `settingsService.updateTeacherSettings()` | 演示态 | 改为写接口 |
| 修改密码 | 提交新密码 | Write API | `settingsService.changePassword()` 或 `authService.changePassword()` | 本地校验演示 | 改为写接口 |
| 头像上传 | 选择并预览头像 | Async workflow | `settingsService.uploadAvatar()` | 前端预览为主 | 改为上传接口 |
| 设备管理弹窗 | 查看在线设备 | Read API | `settingsService.getDevices()` | 演示态 | 后续可选实现 |

### 待办

- [x] 抽取教师 Dashboard 演示数据到 `mocks/dashboard.ts`
- [x] 扩展 `TeacherDashboardData`
- [x] 新增创建课程相关写接口
- [x] 新增教师通知服务
- [x] 新增教师设置服务
- [x] 页面改为 service 驱动

---

## 3. 管理员 Dashboard

### 文件

- `src/pages/admin-dashboard/page.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 顶部 tab 切换 | `overview / users / courses / audit / settings` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 用户菜单展开/收起 | 打开菜单、关闭菜单 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 退出登录 | 点击退出 | Write API | `authService.logout()` | 仅跳转登录页 | 改为真实退出 |
| 系统概览 | 平台总览、活跃数据 | Read API | `dashboardService.getAdminDashboard()` | 页面内硬编码 | 需补 service/type/mock |
| 用户管理列表 | 用户列表、状态、筛选 | Read API | `adminService.getUsers()` 或 admin dashboard 子接口 | 页面内硬编码 | 后续抽离 |
| 用户管理动作 | 启用/禁用/查看详情 | Write API | `adminService.updateUserStatus()` | 演示态 | 需补接口 |
| 课程管理列表 | 课程列表、状态 | Read API | `adminService.getCourses()` | 页面内硬编码 | 需补接口 |
| 课程管理动作 | 上架/下架/审核 | Write API | `adminService.updateCourseStatus()` | 演示态 | 需补接口 |
| 内容审核列表 | 审核队列 | Read API | `adminService.getAuditQueue()` | 页面内硬编码 | 需补接口 |
| 审核动作 | 通过/拒绝/查看原因 | Write API | `adminService.reviewContent()` | 演示态 | 需补接口 |
| 系统设置读取 | 平台设置、阈值、开关 | Read API | `adminService.getSystemSettings()` | 页面内硬编码 | 需补接口 |
| 系统设置保存 | 保存系统配置 | Write API | `adminService.updateSystemSettings()` | 演示态 | 需补接口 |

### 待办

- [x] 新增 `src/types/admin-dashboard.ts` 或并入 `types/dashboard.ts`
- [x] 新增 `src/mocks/admin-dashboard.ts`
- [x] 扩展 `src/services/dashboard.ts` 以支持管理员概览
- [x] 视需要新增 `src/services/admin.ts`
- [x] 页面改为 service 驱动

---

## 4. 学生课程页

### 文件

- `src/pages/student-course/page.tsx`
- `src/pages/student-course/components/MyLearning.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 侧边 section 切换 | `home / materials / tasks / interaction / ai / flashcards / mylearning` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 页面 bootstrap | 课程名、教师、课程码、默认 section | Read API | `courseService.getStudentCourseBootstrap(courseId)` | 页面只拿 URL 参数，未走 service | 改为 bootstrap 接口 |
| 课程首页概览 | banner、统计、快捷入口 | Read API | `courseService.getStudentCourseHome()` | 页面硬编码 | 抽离 |
| 资料列表 | 资料卡片、搜索、分类、预览 | Read API | `courseService.getStudentCourseMaterials()` | 页面硬编码 | 抽离 |
| 资料预览 / AI 解析 | 打开预览、查看 AI 总结 | Read API / Async workflow | `courseService.getMaterialPreview()`、`aiService.getMaterialAnalysis()` | 弹窗演示态 | 后续接口化 |
| 任务中心读取 | 作业/考试/通知列表 | Read API | `courseService.getStudentCourseTasks()` | 页面硬编码 | 抽离 |
| 开始作业 / 考试 | 进入答题流程 | Read API + Write API | `courseService.getTaskDetail()`、`courseService.submitHomework()` | 演示态 | 后续接口化 |
| 查看批改 | 查看得分与解析 | Read API | `courseService.getHomeworkResult()` | 页面硬编码 | 抽离 |
| 错题本 | 查看、添加、筛选错题 | Read API + Write API | `learningService.getMistakes()`、`learningService.createMistake()` | 页面硬编码 | 抽离 |
| 互动问答 | 提问列表、展开回复 | Read API | `courseService.getQuestions()` | 页面硬编码 | 抽离 |
| 新增提问 | 发问题、传附件 | Write API | `courseService.createQuestion()` | 演示态 | 后续接口化 |
| 回复问题 | 针对问题回复 | Write API | `courseService.replyQuestion()` | 演示态 | 后续接口化 |
| 讨论区列表 | 讨论贴、回复、点赞、置顶状态 | Read API | `courseService.getDiscussions()` | 页面硬编码 | 抽离 |
| 发起讨论 | 新建讨论 | Write API | `courseService.createDiscussion()` | 演示态 | 接口化 |
| 讨论点赞 | 点赞 / 取消点赞 | Write API | `courseService.toggleDiscussionLike()` | 演示态 | 接口化 |
| AI 转教师 | 申请人工答疑 | Write API | `aiService.escalateToTeacher()` | 演示态 | 接口化 |
| 学习闪卡 | 开始学习、答题、翻卡 | Read API + Write API | `learningService.getFlashcards()`、`learningService.submitFlashcardReview()` | 页面硬编码 | 后续接口化 |
| 我的学习 | 学习统计、导出 | Read API + Write API | `learningService.getLearningOverview()`、`learningService.exportLearningData()` | 组件内硬编码 | 抽离 |

### 待办

- [x] 扩展 `StudentCourseBootstrapData`
- [x] 拆分课程页数据类型：home/materials/tasks/questions/discussions/flashcards/learning
- [x] 将页面硬编码业务数组迁移到 `mocks/course.ts` 和 `mocks/learning.ts`
- [x] 扩展 `courseService`
- [x] 可选新增 `learningService`
- [x] 页面分区逐步改为 service 驱动

进展：学生课程首页概览、知识图谱节点、课程资料列表、任务列表、我的提问、讨论列表、FAQ 已迁移到 `types/course.ts`、`mocks/course.ts`、`courseService`；错题、闪卡、`MyLearning` 学习统计和导出已迁移到 `types/learning.ts`、`mocks/learning.ts`、`learningService`。剩余：周报/月报详情等展示型细分数据可继续抽离。

---

## 5. 教师课程页

### 文件

- `src/pages/teacher-course/page.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 侧边 section 切换 | `home / knowledge / tasks / interaction / students / ai` | Local UI only | 无 | 已实现 | 保持本地状态 |
| 页面 bootstrap | 课程名、课程码、学生数 | Read API | `courseService.getTeacherCourseBootstrap(courseId)` | 已接入 service | 继续按后端字段扩展 |
| 首页概览数据 | 课程统计、活跃流、预警学生 | Read API | `courseService.getTeacherCourseHome()` | 已接入 service | 继续补充细分接口 |
| 邀请码复制 | 复制邀请码 | Local UI only / Read API | 可由 bootstrap 提供 | 已实现 | 保持本地，数据来自接口 |
| 资料上传 | 拖拽、选择文件、上传进度 | Async workflow | `courseService.uploadMaterials()` | 前端模拟进度 | 接口化 |
| 资料列表 | 展开/折叠、筛选、排序 | Read API | `courseService.getTeacherCourseMaterials()` | 已接入 service | 继续补筛选/分页参数 |
| 资料操作 | 预览 / 下载 / AI 分析 / 重命名 / 分享 / 删除 | Read API + Write API + Async workflow | `courseService.getTeacherCourseMaterialPreview()`、`courseService.downloadTeacherCourseFile()`、`courseService.getTeacherCourseMaterialAnalysis()` 及对应写接口 | 预览 / 下载 / 解析详情已接入 service，部分操作仍演示态 | 继续补分享与预览流真实地址 |
| 知识图谱 | 节点展开、重置、全屏 | Read API + Local UI only | `courseService.getKnowledgeGraph()` | 已接入 service | 保持本地 UI 交互 |
| 发布通知 | 打开弹窗、填写表单、发布 | Write API | `courseService.publishNotice()` | 演示态 | 接口化 |
| 创建作业 | 填表、题目维护、附件上传、发布 | Write API + Async workflow | `courseService.createHomework()` | 演示态 | 接口化 |
| 生成试题 | AI 自动生成题目 | Async workflow | `aiService.generateExamQuestions()` | 演示态 | 接口化 |
| 创建考试 | 配置考试并发布 | Write API | `courseService.createExam()` | 演示态 | 接口化 |
| 任务列表读取 | 通知/作业/考试 | Read API | `courseService.getTeacherCourseTasks()` | 已接入 service | 继续补分页/筛选参数 |
| 任务详情 | 查看提交率、学生情况 | Read API | `courseService.getTeacherCourseTaskDetail()` | 已接入 service | 后续对接真实详情字段 |
| 问答区 | 问题列表、展开、教师回复、查看 AI 回答、采纳 AI 回答 | Read API + Write API | `courseService.getTeacherCourseQuestions()`、`aiService.getTeacherAiQuestionDetail()`、`aiService.adoptAiAnswer()`、`courseService.replyTeacherQuestion()` | 列表与 AI 回答详情已接入 service | 继续补更细粒度联动字段 |
| 讨论区 | 发起讨论、回复、点赞、置顶 | Read API + Write API | `courseService.getCourseDiscussions('teacher', courseId)`、`courseService.createDiscussion()`、`courseService.togglePinDiscussion()` | 列表已接入 service，部分交互仍演示态 | 继续补交互细节 |
| 学生管理 | 分组、筛选、预警、提醒、导出 | Read API + Write API | `courseService.getTeacherCourseStudents()`、`courseService.sendWarningReminder()`、`courseService.moveStudentsToGroup()`、`courseService.exportStudents()` | 已接入 service | 继续补筛选/详情字段 |

### 待办

- [x] 扩展 `TeacherCourseBootstrapData`
- [x] 拆分教师课程页业务类型
- [x] 将课程页演示数据迁移到 `mocks/course.ts`
- [x] 扩展 `courseService`
- [x] 与 `aiService` 建立联动
- [x] 页面各分区逐步改为 service 驱动

进展：教师课程首页概览、知识图谱节点、教师资料列表、资料预览/下载链路、资料 AI 解析详情、任务列表、任务详情、问答列表、问答 AI 回答详情、学生管理、讨论列表已迁移到 `types/course.ts`、`mocks/course.ts`、`courseService` / `aiService`，页面通过 service 初始化；后续可继续补分享与预览流真实地址、任务详情真实字段、问答更细粒度 AI 联动等细分接口。

---

## 6. 学生 AI 助教

### 文件

- `src/pages/student-course/components/AIAssistant.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 左侧会话列表读取 | 会话列表、当前会话 | Read API | `aiService.getStudentConversations()` | 本地 state | 接口化 |
| 新建会话 | 点击新建 | Write API | `aiService.createConversation()` | 本地 state | 接口化 |
| 切换会话 | 点击列表项 | Read API | `aiService.getConversationMessages(conversationId)` | 本地切换 | 接口化 |
| 删除会话 | 删除单条会话 | Write API | `aiService.deleteConversation(id)` | 本地 state | 接口化 |
| 展开/收起对话栏 | 手柄切换 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 消息列表读取 | 消息、附件、引用来源 | Read API | `aiService.getConversationMessages()` | 本地 state | 接口化 |
| 发送消息 | 文本消息 | Write API | `aiService.sendMessage()` | 本地模拟 AI 回复 | 接口化 |
| 上传附件 | 图片/文档/代码 | Async workflow | `aiService.uploadAttachment()` | 本地预览 | 接口化 |
| 拖拽上传 | drag/drop 上传 | Async workflow | `aiService.uploadAttachment()` | 本地 | 接口化 |
| 快捷提示词 | 点击填充输入框 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 点赞回答 | like AI message | Write API | `aiService.likeMessage(messageId)` | 本地 state | 接口化 |
| 点踩回答 | dislike AI message | Write API | `aiService.dislikeMessage(messageId)` | 本地 state | 接口化 |
| 点踩补充说明 | 提交原因并转教师 | Write API | `aiService.submitFeedback()` 或 `aiService.escalateToTeacher()` | 本地演示 | 接口化 |
| 右侧工具 tab | `quick / recommend / source` | Local UI only + Read API | 推荐与溯源数据可走接口 | 目前主要本地 | 后续拆分 |
| 右侧推荐动作 | 点击推荐 prompt | Local UI only | 无 | 已实现 | 保持本地状态 |
| 右侧溯源内容 | 来源列表 | Read API | `aiService.getMessageSources(messageId)` | 本地 state | 接口化 |
| 切换知识库 | `course / personal` | Write API + Read API | `aiService.updateConversationContext()` | 本地 state | 接口化 |
| 切换回答风格 | `academic / inspire / debug` | Write API + Read API | `aiService.updateConversationStyle()` | 本地 state | 接口化 |

### 待办

- [x] 新增 `src/types/ai.ts`
- [x] 新增 `src/mocks/ai.ts`
- [x] 新增 `src/services/ai.ts`
- [x] 将学生 AI 助教中的本地会话/消息迁移到 mock + service
- [x] 所有点踩/点赞/转教师动作统一挂到 `aiService`

---

## 7. 教师 AI 助教

### 文件

- `src/pages/teacher-course/components/TeacherAIAssistant.tsx`

### 功能-接口对照

| 功能块 | 当前交互 | 类型 | 建议接口/服务 | 当前状态 | 后续任务 |
|---|---|---|---|---|---|
| 左侧会话列表 | 会话读取、切换、新建、删除 | Read API + Write API | `aiService.getTeacherConversations()` 等 | 已接入 service | 继续补服务端持久化细节 |
| 展开/收起对话栏 | 手柄切换 | Local UI only | 无 | 已实现 | 保持本地状态 |
| 消息区 | 教师会话消息、附件、发送 | Read API + Write API + Async workflow | `aiService.getConversationMessages()`、`aiService.sendMessage()`、`aiService.uploadAttachment()` | 已接入 service | 继续补消息持久化细节 |
| 右侧 tab 切换 | `aiQuestions / feedback / tools / sources` | Local UI only | 无 | 已实现 | 保持本地状态 |
| AI 问题队列读取 | 低置信回答队列、展开详情 | Read API | `aiService.getTeacherAiQuestions()` | 已接入 service | 保持前端筛选展开逻辑 |
| AI 问题人工回复 | 发送教师回复 | Write API | `aiService.replyAiQuestion()` | 已接入 service | 后续补细粒度返回字段 |
| 采纳 AI 回答 | adopt AI answer | Write API | `aiService.adoptAiAnswer()` | 已接入 service | 后续补写后刷新策略 |
| 学生反馈列表读取 | 反馈队列、详情弹窗 | Read API | `aiService.getFeedbackQueue()` | 已接入 service | 后续补分页/筛选字段 |
| 标记反馈已处理 | resolve feedback | Write API | `aiService.resolveFeedback()` | 已接入 service | 后续补写后刷新策略 |
| 工具区动作 | 生成教案 / 生成试卷 / 学情分析 / 生成卡组 | Async workflow | `aiService.generateLessonPlan()`、`generateExam()`、`generateLearningAnalysis()`、`generateFlashcards()` | 已接入 service 并增加异步状态 | 后续补结果持久化 |
| 溯源区 | 显示消息来源 | Read API | `aiService.getMessageSources()` | 已接入 service | 后续补按消息切换来源 |
| 切换知识库 | `course / global` | Write API + Read API | `aiService.updateConversationContext()` | 已接入 service | 后续补读回显 |
| 切换回答风格 | `academic / inspire / debug` | Write API + Read API | `aiService.updateConversationStyle()` | 已接入 service | 后续补读回显 |

### 待办

- [x] 将教师 AI 助教的 AI 问题、反馈、溯源、工具区全部纳入 `aiService`
- [x] 为反馈详情、采纳 AI、人工回复设计清晰写接口
- [x] 为工具区生成动作增加异步状态管理

---

## Recommended Execution Order

### Stage A 低风险高收益

- [x] 补齐 Dashboard types/mocks/services
- [x] 增加管理员 Dashboard mock/type/service
- [x] 三个 Dashboard 页面改为 service 驱动
- [x] 三个 Dashboard 退出登录统一走 `authService.logout()`

### Stage B 课程页壳层接线

- [x] 扩展课程 bootstrap 类型
- [x] 学生课程页接 `getStudentCourseBootstrap`
- [x] 教师课程页接 `getTeacherCourseBootstrap`
- [x] 课程页顶部、基础统计和基础列表改为 service 驱动

### Stage C AI 助教服务化

- [x] 建立 `aiService`
- [x] 学生 AI 助教接会话列表、消息列表、发送消息
- [x] 教师 AI 助教接会话列表、消息列表、AI 问题队列、反馈队列
- [x] 点赞/点踩/转教师/采纳 AI 全部变成真实写接口占位

### Stage D 设置与剩余写动作

- [x] 学生设置接 `settingsService`
- [x] 教师设置接 `settingsService`
- [x] 加课、创建课程、发布任务、发布讨论、上传资料逐步接口化

### Stage E 联调文档输出

- [x] 产出接口字段清单
- [x] 产出 demo 账号数据说明
- [x] 产出普通账号空状态说明

---

## Definition of Done

达到“便于后端联调”的状态，至少满足以下条件：

- 页面里不再散落大量业务演示数组
- 所有主要业务数据都通过 `services/*` 获取
- 所有重要按钮都能映射到明确的未来读写接口
- 普通账号在零数据情况下有空状态
- demo 账号模式和普通账号模式能共存
- 登录态、退出登录和基本守卫可用

