import { useEffect, useState } from "react";
import { courseService } from "@/services/course";
import type {
  CourseSummary,
  StudentCourseBootstrapData,
  TeacherCourseBootstrapData,
} from "@/types/course";

export type CourseBootstrapRole = "student" | "teacher";

type BootstrapDataByRole<Role extends CourseBootstrapRole> =
  Role extends "student" ? StudentCourseBootstrapData : TeacherCourseBootstrapData;

const DEFAULT_COURSE_SUMMARY: CourseSummary = {
  id: "unknown",
  name: "未知课程",
  teacher: "未知教师",
  code: "UNKNOWN",
};

export function useCourseBootstrap<Role extends CourseBootstrapRole>(
  courseId: string | undefined,
  role: Role,
) {
  const [bootstrap, setBootstrap] = useState<BootstrapDataByRole<Role> | null>(null);
  const [course, setCourse] = useState<CourseSummary>({
    ...DEFAULT_COURSE_SUMMARY,
    id: courseId || DEFAULT_COURSE_SUMMARY.id,
  });
  const [courseError, setCourseError] = useState("");

  useEffect(() => {
    if (!courseId) {
      setCourseError("课程ID不存在");
      setCourse({
        ...DEFAULT_COURSE_SUMMARY,
        id: DEFAULT_COURSE_SUMMARY.id,
      });
      setBootstrap(null);
      return;
    }

    let mounted = true;
    const loadBootstrap =
      role === "student"
        ? courseService.getStudentCourseBootstrap
        : courseService.getTeacherCourseBootstrap;

    setCourse((currentCourse) => ({
      ...currentCourse,
      id: courseId,
    }));

    loadBootstrap(courseId)
      .then((data) => {
        if (!mounted) return;
        setBootstrap(data as BootstrapDataByRole<Role>);
        setCourse(data.course);
        setCourseError("");
      })
      .catch((error) => {
        if (!mounted) return;
        setCourseError(
          error instanceof Error ? error.message : "课程基础信息加载失败",
        );
        setBootstrap(null);
      });

    return () => {
      mounted = false;
    };
  }, [courseId, role]);

  return { bootstrap, course, courseError };
}
