# Backend Interface Field Checklist

## Purpose

这份清单用于前后端联调时快速对齐“前端已经接好的接口”与“后端至少需要返回哪些核心字段”。

原则：

- 优先列出已经 service 化的页面接口
- 只写高频、关键字段，不把文档写成 OpenAPI
- 真实联调时允许后端补充更多字段，但尽量不要缺少这里的核心字段

---

## 1. Dashboard

### `GET /student/dashboard`

核心字段：

- `greetingName`
- `stats.activeCourses`
- `stats.pendingTasks`
- `stats.completionRate`
- `pendingItems[]`
- `progressCourses[]`
- `recommendations[]`
- `activities[]`
- `notifications[]`
- `courses[]`

### `GET /teacher/dashboard`

核心字段：

- `greetingName`
- `stats.activeCourses`
- `stats.totalStudents`
- `stats.pendingReviews`
- `stats.aiAnswerRate`
- `calendarEvents[]`
- `courses[]`
- `notifications[]`
- `weeklyFocus[]`
- `studentAlerts[]`

### `GET /admin/dashboard`

核心字段：

- `stats[]`
- `todoReminders[]`
- `activities[]`
- `systemStatus[]`
- `userReviews[]`
- `users[]`
- `courses[]`
- `auditAnswers[]`
- `auditReports[]`
- `sensitiveWords[]`

---

## 2. Course Shell

### `GET /student/courses/:courseId`

核心字段：

- `course.id`
- `course.name`
- `course.teacher`
- `course.code`

### `GET /teacher/courses/:courseId`

核心字段：

- `course.id`
- `course.name`
- `course.teacher`
- `course.code`

建议补充：

- `studentCount`
- `inviteCode`
- `defaultSection`

---

## 3. Student Course

### `GET /student/courses/:courseId/home`

核心字段：

- `welcome`
- `quickActions[]`
- `notices[]`
- `upcomingTasks[]`
- `todayUpdates[]`
- `classActivities[]`
- `milestones[]`
- `progress`

### `GET /student/courses/:courseId/materials`

核心字段：

- `files[].id`
- `files[].name`
- `files[].type`
- `files[].size`
- `files[].date`
- `files[].views`

### `GET /student/courses/:courseId/tasks`

核心字段：

- `tasks[].id`
- `tasks[].type`
- `tasks[].title`
- `tasks[].status`
- `tasks[].deadline`
- `tasks[].score`

### `GET /student/courses/:courseId/questions`

核心字段：

- `questions[].id`
- `questions[].question`
- `questions[].status`
- `questions[].time`
- `questions[].replies[]`

### `GET /student/courses/:courseId/discussions`

核心字段：

- `discussions[].id`
- `discussions[].author`
- `discussions[].title`
- `discussions[].content`
- `discussions[].likes`
- `discussions[].replies[]`

### `GET /student/courses/:courseId/faqs`

核心字段：

- `faqs[].id`
- `faqs[].question`
- `faqs[].answer`
- `faqs[].category`

---

## 4. Teacher Course

### `GET /teacher/courses/:courseId/home`

核心字段：

- `inviteCode`
- `stats[]`
- `recentTasks[]`
- `warningStudents[]`
- `activities[]`
- `weeklyStats[]`
- `groupPerformance[]`

### `GET /teacher/courses/:courseId/materials`

核心字段：

- `files[].id`
- `files[].name`
- `files[].type`
- `files[].size`
- `files[].status`
- `files[].date`
- `files[].category`
- `files[].downloads`

### `GET /teacher/courses/:courseId/materials/:fileId/preview`

核心字段：

- `fileId`
- `previewType`
- `previewUrl`
- `note`
- `pageCount`
- `durationText`

### `GET /teacher/courses/:courseId/materials/:fileId/download`

核心字段：

- `fileId`
- `fileName`
- `downloadUrl`

### `GET /teacher/courses/:courseId/materials/:fileId/analysis`

核心字段：

- `fileId`
- `summary`
- `keyPoints[]`
- `difficulties[]`
- `recommendedStudyDuration`
- `generatedAt`

### `GET /teacher/courses/:courseId/tasks`

核心字段：

- `tasks[].id`
- `tasks[].type`
- `tasks[].title`
- `tasks[].status`
- `tasks[].publishDate`
- `tasks[].deadline`
- `tasks[].submitted`
- `tasks[].total`

### `GET /teacher/courses/:courseId/tasks/:taskId`

核心字段：

- `id`
- `type`
- `title`
- `description`
- `requirements[]`
- `status`
- `participantCount`
- `submitted`
- `total`
- `submissions[]`

### `GET /teacher/courses/:courseId/questions`

核心字段：

- `questions[].id`
- `questions[].student`
- `questions[].question`
- `questions[].confidence`
- `questions[].status`
- `questions[].replies[]`

### `GET /teacher/courses/:courseId/students`

核心字段：

- `students[].id`
- `students[].name`
- `students[].studentId`
- `students[].group`
- `students[].progress`
- `students[].homework`
- `students[].attendance`
- `students[].status`

### `GET /teacher/courses/:courseId/discussions`

核心字段：

- `discussions[].id`
- `discussions[].author`
- `discussions[].title`
- `discussions[].content`
- `discussions[].likes`
- `discussions[].pinned`
- `discussions[].replies[]`

---

## 5. Learning

### `GET /learning/mistakes`

核心字段：

- `mistakes[].id`
- `mistakes[].question`
- `mistakes[].chapter`
- `mistakes[].analysis`
- `mistakes[].mastered`

### `GET /learning/flashcards`

核心字段：

- `decks[].id`
- `decks[].title`
- `decks[].description`
- `decks[].cards[]`

### `GET /learning/overview`

核心字段：

- `summaryCards[]`
- `radar[]`
- `keywords[]`
- `weeklyHours[]`
- `chapterProgress[]`

---

## 6. AI

### `GET /student/ai/conversations`

核心字段：

- `id`
- `title`
- `createdAt`
- `lastMessage`

### `GET /teacher/ai/conversations`

核心字段：

- `id`
- `title`
- `createdAt`
- `lastMessage`

### `GET /teacher/ai/questions`

核心字段：

- `id`
- `student`
- `avatar`
- `question`
- `aiAnswer`
- `confidence`
- `confidenceLevel`
- `sources[]`
- `status`
- `teacherReply`

### `GET /teacher/ai/questions/:questionId`

核心字段：

- 与列表项保持一致
- 至少保证 `aiAnswer`、`confidence`、`sources[]` 完整

### `GET /teacher/ai/feedback`

核心字段：

- `id`
- `studentName`
- `conversationTitle`
- `questionContent`
- `aiAnswer`
- `reason`
- `timestamp`
- `status`

### `GET /ai/messages/:messageId/sources`

核心字段：

- `name`
- `page`
- `type`

---

## 7. Settings

### `GET /student/settings`

核心字段：

- `profile`
- `academic`
- `notifications`
- `preferences`
- `privacy`

### `GET /teacher/settings`

核心字段：

- `profile`
- `notifications`
- `ai`
- `achievements`

---

## 8. Write API Minimal Rule

所有写接口联调时至少保证：

- 成功时返回 `200/201/204`
- 失败时返回明确错误信息
- 不要只返回字符串，尽量保持对象结构

建议统一：

- `message`
- `success`
- `data`

