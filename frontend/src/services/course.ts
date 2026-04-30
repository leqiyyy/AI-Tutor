import { http } from "@/lib/http";
import { shouldUseMockApi } from "@/lib/env";
import {
  getMockCourseFaqs,
  getMockCourseKnowledgeGraph,
  getMockCourseDiscussions,
  getMockStudentCourseMaterials,
  getMockStudentCourseBootstrap,
  getMockStudentCourseDiscussions,
  getMockStudentCourseHome,
  getMockStudentCourseQuestions,
  getMockStudentCourseTasks,
  getMockTeacherCourseHome,
  getMockTeacherCourseMaterialAnalysis,
  getMockTeacherCourseMaterialDownload,
  getMockTeacherCourseMaterialPreview,
  getMockTeacherCourseMaterials,
  getMockTeacherCourseBootstrap,
  getMockTeacherCourseQuestions,
  getMockTeacherCourseStudents,
  getMockTeacherCourseTaskDetail,
  getMockTeacherCourseTasks,
  mockCreateCourse,
  mockGenerateInviteCode,
  mockJoinCourse,
} from "@/mocks/course";
import type {
  CourseFaqsData,
  CreateCourseRequest,
  CreateCourseResult,
  CourseDiscussionsData,
  CourseRole,
  GenerateInviteCodeResult,
  JoinCourseRequest,
  JoinCourseResult,
  KnowledgeGraphData,
  StudentCourseBootstrapData,
  StudentCourseHomeData,
  StudentCourseMaterialsData,
  StudentCourseQuestionsData,
  StudentCourseTasksData,
  TeacherCourseBootstrapData,
  TeacherCourseHomeData,
  TeacherCourseMaterialAnalysisDetail,
  TeacherCourseMaterialDownloadData,
  TeacherCourseMaterialPreviewData,
  TeacherCourseMaterialsData,
  TeacherCourseQuestionsData,
  TeacherCourseStudentsData,
  TeacherCourseTaskDetail,
  TeacherCourseTasksData,
} from "@/types/course";

type CoursePayload = Record<string, unknown>;
type CourseMutationResult = {
  id?: string | number;
  title?: string;
  recipientCount?: number;
};

function buildFormData(files: File[], extra?: CoursePayload) {
  const formData = new FormData();

  files.forEach((file) => formData.append("files", file));
  Object.entries(extra || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      formData.append(key, String(value));
    }
  });

  return formData;
}

export const courseService = {
  async getStudentCourseBootstrap(
    courseId: string,
  ): Promise<StudentCourseBootstrapData> {
    return shouldUseMockApi
      ? getMockStudentCourseBootstrap(courseId)
      : http<StudentCourseBootstrapData>(`/student/courses/${courseId}`);
  },

  async getTeacherCourseBootstrap(
    courseId: string,
  ): Promise<TeacherCourseBootstrapData> {
    return shouldUseMockApi
      ? getMockTeacherCourseBootstrap(courseId)
      : http<TeacherCourseBootstrapData>(`/teacher/courses/${courseId}`);
  },

  async getKnowledgeGraph(
    courseId: string,
    role: CourseRole,
  ): Promise<KnowledgeGraphData> {
    return shouldUseMockApi
      ? getMockCourseKnowledgeGraph(courseId)
      : http<KnowledgeGraphData>(`/${role}/courses/${courseId}/knowledge-graph`);
  },

  async getStudentCourseMaterials(
    courseId: string,
  ): Promise<StudentCourseMaterialsData> {
    return shouldUseMockApi
      ? getMockStudentCourseMaterials()
      : http<StudentCourseMaterialsData>(`/student/courses/${courseId}/materials`);
  },

  async getStudentCourseHome(courseId: string): Promise<StudentCourseHomeData> {
    return shouldUseMockApi
      ? getMockStudentCourseHome()
      : http<StudentCourseHomeData>(`/student/courses/${courseId}/home`);
  },

  async getStudentCourseTasks(courseId: string): Promise<StudentCourseTasksData> {
    return shouldUseMockApi
      ? getMockStudentCourseTasks()
      : http<StudentCourseTasksData>(`/student/courses/${courseId}/tasks`);
  },

  async getStudentCourseQuestions(
    courseId: string,
  ): Promise<StudentCourseQuestionsData> {
    return shouldUseMockApi
      ? getMockStudentCourseQuestions()
      : http<StudentCourseQuestionsData>(`/student/courses/${courseId}/questions`);
  },

  async getCourseFaqs(courseId: string): Promise<CourseFaqsData> {
    return shouldUseMockApi
      ? getMockCourseFaqs()
      : http<CourseFaqsData>(`/student/courses/${courseId}/faqs`);
  },

  async getTeacherCourseMaterials(
    courseId: string,
  ): Promise<TeacherCourseMaterialsData> {
    return shouldUseMockApi
      ? getMockTeacherCourseMaterials()
      : http<TeacherCourseMaterialsData>(`/teacher/courses/${courseId}/materials`);
  },

  async getTeacherCourseMaterialAnalysis(
    courseId: string,
    fileId: string | number,
  ): Promise<TeacherCourseMaterialAnalysisDetail> {
    return shouldUseMockApi
      ? getMockTeacherCourseMaterialAnalysis(Number(fileId))
      : http<TeacherCourseMaterialAnalysisDetail>(
          `/teacher/courses/${courseId}/materials/${fileId}/analysis`,
        );
  },

  async getTeacherCourseMaterialPreview(
    courseId: string,
    fileId: string | number,
  ): Promise<TeacherCourseMaterialPreviewData> {
    return shouldUseMockApi
      ? getMockTeacherCourseMaterialPreview(Number(fileId))
      : http<TeacherCourseMaterialPreviewData>(
          `/teacher/courses/${courseId}/materials/${fileId}/preview`,
        );
  },

  async downloadTeacherCourseFile(
    courseId: string,
    fileId: string | number,
  ): Promise<TeacherCourseMaterialDownloadData> {
    return shouldUseMockApi
      ? getMockTeacherCourseMaterialDownload(Number(fileId))
      : http<TeacherCourseMaterialDownloadData>(
          `/teacher/courses/${courseId}/materials/${fileId}/download`,
        );
  },

  async getTeacherCourseHome(courseId: string): Promise<TeacherCourseHomeData> {
    return shouldUseMockApi
      ? getMockTeacherCourseHome()
      : http<TeacherCourseHomeData>(`/teacher/courses/${courseId}/home`);
  },

  async getTeacherCourseTasks(courseId: string): Promise<TeacherCourseTasksData> {
    return shouldUseMockApi
      ? getMockTeacherCourseTasks()
      : http<TeacherCourseTasksData>(`/teacher/courses/${courseId}/tasks`);
  },

  async getTeacherCourseTaskDetail(
    courseId: string,
    taskId: string | number,
  ): Promise<TeacherCourseTaskDetail> {
    return shouldUseMockApi
      ? getMockTeacherCourseTaskDetail(Number(taskId))
      : http<TeacherCourseTaskDetail>(`/teacher/courses/${courseId}/tasks/${taskId}`);
  },

  async getTeacherCourseQuestions(
    courseId: string,
  ): Promise<TeacherCourseQuestionsData> {
    return shouldUseMockApi
      ? getMockTeacherCourseQuestions()
      : http<TeacherCourseQuestionsData>(`/teacher/courses/${courseId}/questions`);
  },

  async getTeacherCourseStudents(
    courseId: string,
  ): Promise<TeacherCourseStudentsData> {
    return shouldUseMockApi
      ? getMockTeacherCourseStudents()
      : http<TeacherCourseStudentsData>(`/teacher/courses/${courseId}/students`);
  },

  async getCourseDiscussions(
    role: CourseRole,
    courseId: string,
  ): Promise<CourseDiscussionsData> {
    return shouldUseMockApi
      ? role === "student"
        ? getMockStudentCourseDiscussions()
        : getMockCourseDiscussions()
      : http<CourseDiscussionsData>(`/${role}/courses/${courseId}/discussions`);
  },

  async joinCourse(payload: JoinCourseRequest): Promise<JoinCourseResult> {
    return shouldUseMockApi
      ? mockJoinCourse(payload)
      : http<JoinCourseResult>("/student/courses/join", {
          method: "POST",
          body: payload,
        });
  },

  async createCourse(
    payload: CreateCourseRequest,
  ): Promise<CreateCourseResult> {
    return shouldUseMockApi
      ? mockCreateCourse(payload)
      : http<CreateCourseResult>("/teacher/courses", {
          method: "POST",
          body: payload,
        });
  },

  async generateInviteCode(
    courseId: string,
  ): Promise<GenerateInviteCodeResult> {
    return shouldUseMockApi
      ? mockGenerateInviteCode(courseId)
      : http<GenerateInviteCodeResult>(
          `/teacher/courses/${courseId}/invite-code`,
          {
            method: "POST",
          },
        );
  },

  async uploadTeacherCourseFiles(courseId: string, files: File[]): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/files`, {
      method: "POST",
      body: buildFormData(files),
      query: { async_index: true },
    });
  },

  async renameTeacherCourseFile(
    courseId: string,
    fileId: string | number,
    name: string,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/files/${fileId}`, {
      method: "PATCH",
      body: { name },
    });
  },

  async deleteTeacherCourseFile(
    courseId: string,
    fileId: string | number,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/files/${fileId}`, {
      method: "DELETE",
    });
  },

  async retryTeacherCourseFileIndex(
    courseId: string,
    fileId: string | number,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/files/${fileId}/kb/retry`, {
      method: "POST",
      query: { force: true, async_retry: true },
    });
  },

  async rebuildTeacherCourseKnowledge(courseId: string): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/kb/rebuild`, {
      method: "POST",
    });
  },

  async shareTeacherCourseFile(
    courseId: string,
    fileId: string | number,
    payload: CoursePayload = {},
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/files/${fileId}/share`, {
      method: "POST",
      body: payload,
    });
  },

  async publishNotice(courseId: string, payload: CoursePayload): Promise<CourseMutationResult> {
    if (shouldUseMockApi) return {};

    return http<CourseMutationResult>(`/teacher/courses/${courseId}/notices`, {
      method: "POST",
      body: payload,
    });
  },

  async createHomework(courseId: string, payload: CoursePayload): Promise<CourseMutationResult> {
    if (shouldUseMockApi) return {};

    return http<CourseMutationResult>(`/teacher/courses/${courseId}/homeworks`, {
      method: "POST",
      body: payload,
    });
  },

  async createExam(courseId: string, payload: CoursePayload): Promise<CourseMutationResult> {
    if (shouldUseMockApi) return {};

    return http<CourseMutationResult>(`/teacher/courses/${courseId}/exams`, {
      method: "POST",
      body: payload,
    });
  },

  async updateTeacherCourseTaskStatus(
    courseId: string,
    taskId: string | number,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/tasks/${taskId}/status`, {
      method: "PATCH",
      body: payload,
    });
  },

  async replyTeacherQuestion(
    courseId: string,
    questionId: string | number,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/questions/${questionId}/replies`, {
      method: "POST",
      body: payload,
    });
  },

  async sendWarningReminder(courseId: string, studentId: string | number): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/students/${studentId}/warning-reminders`, {
      method: "POST",
    });
  },

  async moveStudentsToGroup(courseId: string, payload: CoursePayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/students/group`, {
      method: "PATCH",
      body: payload,
    });
  },

  async exportStudents(courseId: string, payload: CoursePayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/students/export`, {
      method: "POST",
      body: payload,
    });
  },

  async createStudentQuestion(courseId: string, payload: CoursePayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/questions`, {
      method: "POST",
      body: payload,
    });
  },

  async replyStudentQuestion(
    courseId: string,
    questionId: string | number,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/questions/${questionId}/replies`, {
      method: "POST",
      body: payload,
    });
  },

  async createDiscussion(
    role: "student" | "teacher",
    courseId: string,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/${role}/courses/${courseId}/discussions`, {
      method: "POST",
      body: payload,
    });
  },

  async replyDiscussion(
    role: "student" | "teacher",
    courseId: string,
    discussionId: string | number,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/${role}/courses/${courseId}/discussions/${discussionId}/replies`, {
      method: "POST",
      body: payload,
    });
  },

  async toggleDiscussionLike(
    role: "student" | "teacher",
    courseId: string,
    discussionId: string | number,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/${role}/courses/${courseId}/discussions/${discussionId}/like`, {
      method: "POST",
    });
  },

  async togglePinDiscussion(
    courseId: string,
    discussionId: string | number,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/teacher/courses/${courseId}/discussions/${discussionId}/pin`, {
      method: "POST",
    });
  },

  async submitHomework(
    courseId: string,
    taskId: string | number,
    payload: CoursePayload,
  ): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/tasks/${taskId}/submissions`, {
      method: "POST",
      body: payload,
    });
  },

  async requestTeacherHelp(courseId: string, payload: CoursePayload): Promise<void> {
    if (shouldUseMockApi) return;

    await http<void>(`/student/courses/${courseId}/teacher-help-requests`, {
      method: "POST",
      body: payload,
    });
  },
};
