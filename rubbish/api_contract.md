# API Contract

## Response Envelope

All API responses use:

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

Error shape:

```json
{
  "code": 400,
  "message": "Bad request",
  "data": null
}
```

Authentication uses:

```http
Authorization: Bearer <access_token>
```

## Authentication

### POST `/api/v1/auth/login`

Request:

```json
{
  "account": "teacher@aitutor.local",
  "password": "Teacher123!",
  "role": "teacher"
}
```

Notes:

- `account` also accepts student ID and teacher ID.

Response:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "token",
    "token_type": "bearer",
    "role": "teacher",
    "user_id": "uuid",
    "real_name": "Wang Teacher"
  }
}
```

### POST `/api/v1/auth/register`

Student request example:

```json
{
  "role": "student",
  "realName": "Li Student",
  "studentId": "2024301001",
  "email": "student@aitutor.local",
  "password": "Student123!",
  "confirmPassword": "Student123!",
  "verifyCode": "123456"
}
```

Teacher request example:

```json
{
  "role": "teacher",
  "realName": "Wang Teacher",
  "teacherId": "T2024001",
  "email": "teacher@aitutor.local",
  "password": "Teacher123!",
  "confirmPassword": "Teacher123!",
  "verifyCode": "123456"
}
```

### GET `/api/v1/auth/me`

Returns current user profile.

## Courses and Classes

### GET `/api/v1/courses`

Returns course cards available to current user.

Response item shape:

```json
{
  "id": "course_uuid",
  "class_id": "class_uuid",
  "name": "Computer Networks",
  "code": "CS301",
  "teacher_name": "Wang Teacher",
  "student_count": 1,
  "invite_code": "CS301A1",
  "unread": 0
}
```

### GET `/api/v1/courses/{course_id}`

Returns course detail with associated accessible classes.

### POST `/api/v1/courses`

Request:

```json
{
  "name": "Computer Networks",
  "code": "CS301",
  "description": "Core networking course",
  "cover_color": "#0f766e"
}
```

### GET `/api/v1/classes`

Returns teacher-owned or student-joined classes.

### GET `/api/v1/classes/{class_id}`

Returns class detail with teacher/course names and member counts.

### POST `/api/v1/classes`

Request:

```json
{
  "name": "CS301 Spring Demo",
  "course_id": "optional_course_uuid",
  "semester": "2026 Spring"
}
```

### POST `/api/v1/classes/join`

Request:

```json
{
  "invite_code": "CS301A1"
}
```

### POST `/api/v1/classes/{class_id}/invite`

Returns existing invite code for teacher-owned class.

## Files and Knowledge Base

### POST `/api/v1/courses/{course_id}/files/upload`

Multipart form fields:

- `file`
- `class_id` optional
- `title` optional
- `description` optional

Response:

```json
{
  "code": 200,
  "message": "File uploaded and indexed",
  "data": {
    "id": "material_uuid",
    "course_id": "course_uuid",
    "class_id": "class_uuid",
    "file_name": "tcp_notes.txt",
    "kb_status": "indexed",
    "parse_task_id": "parse_task_uuid",
    "storage_key": "storage_key"
  }
}
```

### GET `/api/v1/courses/{course_id}/files`

Returns uploaded course files.

### GET `/api/v1/courses/{course_id}/files/{file_id}/preview`

Returns file preview metadata and extracted preview text.

### GET `/api/v1/courses/{course_id}/files/{file_id}/download`

Downloads the stored file.

### GET `/api/v1/courses/{course_id}/files/{file_id}/analysis`

Returns parse summary, keywords, and top chunks for the file.

### GET `/api/v1/courses/{course_id}/kb/status`

Response:

```json
{
  "course_id": "course_uuid",
  "status": "ready",
  "document_count": 1,
  "chunk_count": 1,
  "task_summary": {
    "completed": 1
  },
  "latest_task_id": "parse_task_uuid"
}
```

### POST `/api/v1/courses/{course_id}/kb/rebuild`

Triggers simplified re-indexing for current course.

### GET `/api/v1/courses/{course_id}/graph`

Returns:

```json
{
  "nodes": [],
  "edges": []
}
```

### GET `/api/v1/courses/{course_id}/search?q=...`

Searches parsed course content and returns scored snippets.

### GET `/api/v1/tasks/{task_id}`

Dual use:

- returns task detail when `task_id` is a task
- returns parse task detail when `task_id` is a file parse task

Parse task response example:

```json
{
  "id": "parse_task_uuid",
  "kind": "file_parse",
  "status": "completed",
  "parser_name": "simple",
  "summary": "..."
}
```

## Chat

### POST `/api/v1/chat/query`

Request:

```json
{
  "course_id": "course_uuid",
  "message": "What is slow start in TCP?",
  "session_id": null,
  "attachments": []
}
```

Response:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "session_uuid",
    "message_id": "message_uuid",
    "content": "answer text",
    "sources": [
      {
        "name": "tcp_notes.txt",
        "page": 1,
        "type": "txt",
        "score": 0.91,
        "chunk_id": "tcp_notes-chunk-1"
      }
    ],
    "suggestions": [
      "Can you explain this with an example?"
    ],
    "confidence": 0.85,
    "needs_review": false
  }
}
```

### POST `/api/v1/chat/query-with-image`

Same contract as `/chat/query`, but `attachments` may include image metadata.

### GET `/api/v1/chat/sessions`

Query params:

- `course_id` optional
- `class_id` optional

### GET `/api/v1/chat/sessions/{session_id}/messages`

Returns full message history for the session.

### POST `/api/v1/chat/messages/{message_id}/feedback`

Request:

```json
{
  "feedback": "dislike",
  "reason": "Need a clearer explanation"
}
```

## Reviews

### GET `/api/v1/reviews/pending`

Query params:

- `course_id` optional
- `class_id` optional

Returns pending teacher review items.

### POST `/api/v1/reviews/{review_id}/submit`

Request:

```json
{
  "teacher_answer": "Teacher-corrected answer",
  "add_to_kb": true
}
```

### POST `/api/v1/reviews/escalate`

Manual student escalation request.

Request:

```json
{
  "course_id": "course_uuid",
  "question_content": "I still do not understand slow start",
  "ai_answer": "previous AI answer",
  "reason": "Need teacher help"
}
```

Response:

```json
{
  "review_id": "review_uuid",
  "status": "resolved",
  "sync_status": "synced",
  "sync_note": "Teacher answer synced to fallback knowledge base"
}
```

## Tasks

### GET `/api/v1/tasks`

Optional query:

- `class_id`

### POST `/api/v1/tasks/{task_id}/submit`

Request:

```json
{
  "content": "My answer",
  "file_path": null
}
```

### GET `/api/v1/tasks/{task_id}/submissions`

- teacher sees class submissions
- student sees own submission only

### POST `/api/v1/tasks`

Request:

```json
{
  "class_id": "class_uuid",
  "title": "Week 2 Homework",
  "description": "Task description",
  "task_type": "homework",
  "max_score": 100,
  "is_published": true
}
```

## Notifications

### GET `/api/v1/notifications`

Optional query:

- `unread_only`

### POST `/api/v1/notifications/mark-read`

Request:

```json
["notification_id_1", "notification_id_2"]
```

### POST `/api/v1/notifications`

Teacher broadcast notification request:

```json
{
  "class_id": "class_uuid",
  "title": "Homework reminder",
  "content": "Please finish Week 2 homework before Friday.",
  "type": "deadline",
  "scope": "students"
}
```

## Flashcards

### GET `/api/v1/flashcards`

Optional query:

- `course_id`
- `class_id`
- `due_only`

### POST `/api/v1/flashcards/{flashcard_id}/review`

Request:

```json
{
  "rating": 4,
  "response": "good"
}
```

Response:

```json
{
  "flashcard_id": "flashcard_uuid",
  "rating": 4,
  "response": "good",
  "interval_days": 3,
  "next_review_at": "datetime",
  "review_count": 1
}
```

## Analytics and Student Profile

### GET `/api/v1/courses/{course_id}/analytics`

Response fields include:

- `question_count`
- `high_frequency_keywords`
- `disliked_question_count`
- `active_student_count`
- `task_completion_rate`
- `hot_topics`
- `pending_review_count`

### GET `/api/v1/students/me/profile`

Response fields include:

- `preferred_courses`
- `strong_topics`
- `weak_topics`
- `total_questions`
- `dislike_count`
- `task_completion_rate`
- `activity_score`
- `last_active_at`

### GET `/api/v1/students/me/reports/weekly`

Returns a weekly student study report snapshot.

### GET `/api/v1/students/me/reports/monthly`

Returns a monthly student study report snapshot.

### GET `/api/v1/students/me/export?format=csv`

Exports a CSV summary for weekly and monthly metrics.

### GET `/api/v1/students/me/mistakes`

Returns the student mistake book.

### POST `/api/v1/students/me/mistakes`

Request:

```json
{
  "chapter": "Transport Layer",
  "question": "What is slow start?",
  "my_answer": "I am not sure",
  "correct_answer": "It is TCP's initial congestion control phase",
  "analysis": "Review congestion window growth."
}
```

### PUT `/api/v1/students/me/mistakes/{mistake_id}/mastered`

Marks a mistake as mastered.

### POST `/api/v1/students/me/mistakes/{mistake_id}/practice`

Updates practice count and last practice time.

## Admin

### GET `/api/v1/admin/overview`

System-level counts for users, classes, and pending reviews.

### GET `/api/v1/admin/users`

Paginated user list.

### GET `/api/v1/admin/courses`

Paginated course list for admin course management.

### GET `/api/v1/admin/model-config`

Returns current lightweight model/runtime config snapshot.

### PUT `/api/v1/admin/model-config`

Request:

```json
{
  "llm_provider": "mock",
  "rag_engine": "mock",
  "storage_backend": "local",
  "email_dev_mode": true
}
```

### GET `/api/v1/admin/settings`

Returns current lightweight runtime settings snapshot.
