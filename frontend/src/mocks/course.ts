import type {
  CreateCourseRequest,
  CreateCourseResult,
  CourseDiscussion,
  CourseDiscussionsData,
  GenerateInviteCodeResult,
  JoinCourseRequest,
  JoinCourseResult,
  KnowledgeGraphData,
  KnowledgeGraphEdge,
  KnowledgeGraphNode,
  CourseFaq,
  CourseFaqsData,
  StudentCourseMaterial,
  StudentCourseMaterialsData,
  StudentCourseBootstrapData,
  StudentCourseHomeData,
  StudentCourseQuestion,
  StudentCourseQuestionsData,
  StudentCourseTask,
  StudentCourseTasksData,
  TeacherCourseFile,
  TeacherCourseMaterialAnalysisDetail,
  TeacherCourseMaterialDownloadData,
  TeacherCourseMaterialPreviewData,
  TeacherCourseHomeData,
  TeacherCourseMaterialsData,
  TeacherCourseBootstrapData,
  TeacherCourseQuestion,
  TeacherCourseQuestionsData,
  TeacherCourseStudent,
  TeacherCourseStudentsData,
  TeacherCourseTaskDetail,
  TeacherCourseTask,
  TeacherCourseTasksData,
} from "@/types/course";

// 用途: 学生课程页 / 教师课程页的课程壳层、首页、资料、任务、问答、讨论、学生管理联调
// 页面来源: student-course/page.tsx、teacher-course/page.tsx
// 未来接口归属: courseService.get*/create*/reply*/publish*/download* 等课程相关接口

const courseMap = {
  "1": { id: "1", name: "计算机网络", teacher: "王教授", code: "CS301" },
  "2": { id: "2", name: "数据结构与算法", teacher: "李教授", code: "CS201" },
  "3": { id: "3", name: "操作系统原理", teacher: "张教授", code: "CS302" },
  "4": { id: "4", name: "数据库系统", teacher: "刘教授", code: "CS303" },
  "5": { id: "5", name: "软件工程", teacher: "陈教授", code: "CS401" },
};

const mockKnowledgeGraphNodes: KnowledgeGraphNode[] = [
  {
    id: "root",
    label: "计算机网络",
    x: 400,
    y: 50,
    parent: null,
    color: "#14b8a6",
  },
  {
    id: "physical",
    label: "物理层",
    x: 200,
    y: 150,
    parent: "root",
    color: "#3b82f6",
  },
  {
    id: "datalink",
    label: "数据链路层",
    x: 350,
    y: 150,
    parent: "root",
    color: "#10b981",
  },
  {
    id: "network",
    label: "网络层",
    x: 500,
    y: 150,
    parent: "root",
    color: "#8b5cf6",
  },
  {
    id: "transport",
    label: "传输层",
    x: 650,
    y: 150,
    parent: "root",
    color: "#f59e0b",
  },
  {
    id: "application",
    label: "应用层",
    x: 800,
    y: 150,
    parent: "root",
    color: "#ec4899",
  },
  {
    id: "tcp",
    label: "TCP协议",
    x: 600,
    y: 250,
    parent: "transport",
    color: "#f59e0b",
  },
  {
    id: "udp",
    label: "UDP协议",
    x: 700,
    y: 250,
    parent: "transport",
    color: "#f59e0b",
  },
  {
    id: "ip",
    label: "IP协议",
    x: 450,
    y: 250,
    parent: "network",
    color: "#8b5cf6",
  },
  {
    id: "routing",
    label: "路由算法",
    x: 550,
    y: 250,
    parent: "network",
    color: "#8b5cf6",
  },
  {
    id: "http",
    label: "HTTP",
    x: 750,
    y: 250,
    parent: "application",
    color: "#ec4899",
  },
  {
    id: "dns",
    label: "DNS",
    x: 850,
    y: 250,
    parent: "application",
    color: "#ec4899",
  },
];

const mockKnowledgeGraphEdges: KnowledgeGraphEdge[] = mockKnowledgeGraphNodes
  .filter((node) => node.parent)
  .map((node) => ({
    id: `edge-${node.parent}-${node.id}`,
    source: node.parent as string,
    target: node.id,
    relationType: "contains",
    color: "#d1d5db",
  }));

const mockStudentCourseMaterials: StudentCourseMaterial[] = [
  {
    id: "chapter-1-intro",
    name: "第1章 计算机网络概述.pdf",
    type: "pdf",
    size: "2.3 MB",
    date: "2024-01-15",
    views: 156,
  },
  {
    id: "chapter-2-physical",
    name: "第2章 物理层.pptx",
    type: "ppt",
    size: "5.8 MB",
    date: "2024-01-22",
    views: 142,
  },
  {
    id: "chapter-3-datalink",
    name: "第3章 数据链路层.pdf",
    type: "pdf",
    size: "3.1 MB",
    date: "2024-02-12",
    views: 134,
  },
  {
    id: "chapter-4-network",
    name: "第4章 网络层.pptx",
    type: "ppt",
    size: "6.5 MB",
    date: "2024-02-28",
    views: 167,
  },
  {
    id: "chapter-5-tcp-congestion",
    name: "第5章 传输层-TCP拥塞控制.pdf",
    type: "pdf",
    size: "4.2 MB",
    date: "2024-03-05",
    views: 189,
  },
  {
    id: "tcp-video",
    name: "TCP三次握手讲解.mp4",
    type: "video",
    size: "45.2 MB",
    date: "2024-02-05",
    views: 189,
  },
  {
    id: "network-code",
    name: "网络层协议分析代码.zip",
    type: "code",
    size: "1.2 MB",
    date: "2024-02-20",
    views: 98,
  },
];

const mockTeacherCourseFiles: TeacherCourseFile[] = [
  {
    id: 1,
    name: "第1章-计算机网络概述.pdf",
    type: "PDF",
    size: "2.3 MB",
    status: "已解析",
    date: "2024-03-15",
    category: "lecture",
    downloads: 156,
  },
  {
    id: 2,
    name: "第2章-物理层.pptx",
    type: "PPT",
    size: "5.8 MB",
    status: "已解析",
    date: "2024-03-18",
    category: "lecture",
    downloads: 142,
  },
  {
    id: 3,
    name: "第3章-数据链路层.pdf",
    type: "PDF",
    size: "3.1 MB",
    status: "解析中",
    date: "2024-03-20",
    category: "lecture",
    downloads: 98,
  },
  {
    id: 4,
    name: "TCP协议详解视频.mp4",
    type: "Video",
    size: "125 MB",
    status: "已解析",
    date: "2024-03-22",
    category: "video",
    downloads: 203,
  },
  {
    id: 5,
    name: "实验指导书.pdf",
    type: "PDF",
    size: "1.8 MB",
    status: "已解析",
    date: "2024-03-10",
    category: "lab",
    downloads: 87,
  },
  {
    id: 6,
    name: "课后习题答案.pdf",
    type: "PDF",
    size: "2.1 MB",
    status: "已解析",
    date: "2024-03-12",
    category: "exercise",
    downloads: 234,
  },
];

const mockTeacherCourseTasks: TeacherCourseTask[] = [
  {
    id: 1,
    type: "homework",
    title: "第3章课后习题",
    deadline: "2024-03-25 23:59",
    submitted: 45,
    total: 68,
    status: "进行中",
    publishDate: "2024-03-18",
    attachments: ["习题文档.pdf"],
  },
  {
    id: 2,
    type: "exam",
    title: "期中考试",
    startTime: "2024-03-28 14:00",
    deadline: "2024-03-28 16:00",
    duration: 90,
    submitted: 0,
    total: 68,
    status: "未开始",
    publishDate: "2024-03-20",
    attachments: ["考试说明.pdf", "答题卡.docx"],
  },
  {
    id: 3,
    type: "notice",
    title: "下周课程调整通知",
    deadline: "-",
    submitted: 68,
    total: 68,
    status: "已发布",
    publishDate: "2024-03-15",
    attachments: [],
  },
  {
    id: 4,
    type: "homework",
    title: "网络协议分析实验",
    deadline: "2024-03-20 23:59",
    submitted: 68,
    total: 68,
    status: "已结束",
    publishDate: "2024-03-10",
    attachments: ["实验指导.pdf"],
  },
];

const mockTeacherCourseMaterialAnalyses: Record<number, TeacherCourseMaterialAnalysisDetail> = {
  1: {
    fileId: 1,
    summary:
      "本讲义系统梳理了计算机网络的基本概念、发展阶段与分层体系结构，重点介绍 OSI 七层模型和 TCP/IP 四层模型的职责划分与典型协议。",
    keyPoints: [
      "计算机网络的定义、组成与分类",
      "OSI 七层模型的层次划分与作用",
      "TCP/IP 协议栈结构及常见协议",
      "常见网络拓扑结构与适用场景",
      "数据传输方式与基本性能指标",
    ],
    difficulties: [
      { title: "OSI 与 TCP/IP 模型映射关系", difficulty: "中等" },
      { title: "分层封装与解封装过程", difficulty: "较难" },
      { title: "吞吐量、时延等性能指标理解", difficulty: "中等" },
    ],
    recommendedStudyDuration: "2-3 小时",
    generatedAt: "2024-03-18 14:30",
  },
  2: {
    fileId: 2,
    summary:
      "视频围绕物理层与数据链路层展开，通过案例演示信号传输、差错检测与帧封装，适合作为协议入门补充材料。",
    keyPoints: [
      "模拟信号与数字信号的基本区别",
      "信道复用与编码方式",
      "MAC 地址与帧结构",
      "CRC 差错检测机制",
    ],
    difficulties: [
      { title: "编码方式对带宽利用率的影响", difficulty: "较难" },
      { title: "CRC 校验原理", difficulty: "中等" },
    ],
    recommendedStudyDuration: "1.5-2 小时",
    generatedAt: "2024-03-20 09:10",
  },
  3: {
    fileId: 3,
    summary:
      "实验指导重点介绍抓包工具使用流程、实验步骤和报告撰写要求，帮助学生完成协议分析实验。",
    keyPoints: [
      "Wireshark 抓包流程",
      "过滤表达式使用方法",
      "协议字段识别与分析",
      "实验报告组织结构",
    ],
    difficulties: [
      { title: "过滤表达式编写", difficulty: "中等" },
      { title: "协议字段关联分析", difficulty: "较难" },
    ],
    recommendedStudyDuration: "2 小时",
    generatedAt: "2024-03-16 16:20",
  },
};

function buildHtmlPreview(title: string, lines: string[]) {
  const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${title}</title>
    <style>
      body { font-family: "Segoe UI", sans-serif; margin: 0; padding: 32px; background: #f8fafc; color: #0f172a; }
      .card { max-width: 880px; margin: 0 auto; background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; }
      h1 { font-size: 28px; margin: 0 0 20px; }
      p { line-height: 1.75; margin: 12px 0; }
      .tag { display: inline-block; margin-bottom: 18px; padding: 6px 10px; background: #ccfbf1; color: #0f766e; border-radius: 999px; font-size: 12px; font-weight: 600; }
    </style>
  </head>
  <body>
    <div class="card">
      <div class="tag">Mock Preview</div>
      <h1>${title}</h1>
      ${lines.map((line) => `<p>${line}</p>`).join("")}
    </div>
  </body>
</html>`;

  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

const mockTeacherCourseMaterialPreviews: Record<number, TeacherCourseMaterialPreviewData> = {
  1: {
    fileId: 1,
    previewType: "document",
    previewUrl: buildHtmlPreview("第1章 计算机网络概述", [
      "本章介绍计算机网络的基本定义、分类方式和发展历史，是整门课程的入门章节。",
      "重点包括网络资源共享、分组交换思想、分层设计理念，以及 OSI 七层模型与 TCP/IP 协议栈的整体结构。",
      "该预览页用于模拟后端返回的文档预览地址，联调时可替换为 PDF 预览流或在线预览 URL。",
    ]),
    note: "当前为 mock 文档预览页，后续可直接替换成后端返回的 PDF 在线预览地址。",
    pageCount: 18,
  },
  2: {
    fileId: 2,
    previewType: "slide",
    previewUrl: buildHtmlPreview("第2章 物理层与数据链路层", [
      "本 PPT 重点讲解物理层信号传输方式、编码方式，以及数据链路层的帧结构与差错控制。",
      "预览链路已经服务化，后端联调时可直接返回 PPT 转码后的在线预览地址。",
    ]),
    note: "当前为 mock 幻灯片预览页，联调时可改为后端返回的 PPT 转码地址。",
    pageCount: 32,
  },
  4: {
    fileId: 4,
    previewType: "video",
    previewUrl: "",
    note: "Mock 环境未提供视频流地址；联调时后端可返回视频播放地址或签名 URL。",
    durationText: "18 分钟",
  },
  5: {
    fileId: 5,
    previewType: "document",
    previewUrl: buildHtmlPreview("实验指导书", [
      "实验指导书包含抓包实验的步骤说明、过滤表达式示例与报告提交要求。",
      "联调时通常由后端返回文档预览地址或对象存储的签名链接。",
    ]),
    note: "该文档预览结构已准备好，可直接承接后端预览地址。",
    pageCount: 12,
  },
  6: {
    fileId: 6,
    previewType: "document",
    previewUrl: buildHtmlPreview("课后习题答案", [
      "本资料用于教师参考与课后讲评，包含典型题目的解答步骤和评分要点。",
      "这里使用 mock HTML 预览代替真实文件流，方便前端先完成联调结构。",
    ]),
    note: "后端可将该地址替换为真实文件预览流。",
    pageCount: 9,
  },
};

function buildFallbackTeacherCourseMaterialAnalysis(
  file: TeacherCourseFile,
): TeacherCourseMaterialAnalysisDetail {
  return {
    fileId: file.id,
    summary: `${file.name} 的 AI 解析结果将在资料详情接口接入后返回，这里先保留后端联调所需的数据结构。`,
    keyPoints: [
      "资料主题识别",
      "核心知识点提取",
      "学习难点分析",
    ],
    difficulties: [
      { title: "等待后端返回具体难点", difficulty: "中等" },
    ],
    recommendedStudyDuration: "待分析",
    generatedAt: file.date,
  };
}

function buildFallbackTeacherCourseMaterialPreview(
  file: TeacherCourseFile,
): TeacherCourseMaterialPreviewData {
  return {
    fileId: file.id,
    previewType:
      file.type === "Video"
        ? "video"
        : file.type === "PPT"
          ? "slide"
          : "document",
    previewUrl: "",
    note: `${file.name} 的预览地址将在联调接口接入后返回，这里先保留预览数据结构。`,
  };
}

const mockTeacherCourseTaskDetails: Record<number, TeacherCourseTaskDetail> = {
  1: {
    ...mockTeacherCourseTasks[0],
    description:
      "围绕第3章网络层核心概念完成课后习题，重点检查 IP 编址、CIDR 表示法和路由转发过程的理解情况。",
    requirements: [
      "完成全部主观题和计算题",
      "提交 PDF 或 Word 版作答文档",
      "在截止时间前上传到课程作业区",
    ],
    participantCount: 68,
    averageScore: 88,
    highestScore: 98,
    lowestScore: 61,
    submissions: [
      {
        id: 1,
        studentName: "张三",
        studentId: "2021001",
        groupName: "第一组",
        status: "graded",
        submittedAt: "2024-03-21 20:15",
        score: 92,
      },
      {
        id: 2,
        studentName: "李四",
        studentId: "2021002",
        groupName: "第一组",
        status: "submitted",
        submittedAt: "2024-03-22 09:42",
      },
      {
        id: 3,
        studentName: "王五",
        studentId: "2021003",
        groupName: "第二组",
        status: "pending",
        submittedAt: "-",
      },
      {
        id: 4,
        studentName: "赵六",
        studentId: "2021004",
        groupName: "第二组",
        status: "graded",
        submittedAt: "2024-03-20 22:08",
        score: 86,
      },
    ],
  },
  2: {
    ...mockTeacherCourseTasks[1],
    description:
      "期中考试覆盖第1章到第5章的基础知识点，采用闭卷线上考试形式，系统按考试开始时间开放答题。",
    requirements: [
      "考试开始前 10 分钟完成设备与网络检查",
      "考试时长 90 分钟，系统自动交卷",
      "主观题请在答题区内作答，不接受线下补交",
    ],
    participantCount: 68,
    averageScore: 0,
    highestScore: 0,
    lowestScore: 0,
    submissions: [
      {
        id: 1,
        studentName: "张三",
        studentId: "2021001",
        groupName: "第一组",
        status: "pending",
        submittedAt: "-",
      },
      {
        id: 2,
        studentName: "李四",
        studentId: "2021002",
        groupName: "第一组",
        status: "pending",
        submittedAt: "-",
      },
      {
        id: 3,
        studentName: "王五",
        studentId: "2021003",
        groupName: "第二组",
        status: "pending",
        submittedAt: "-",
      },
    ],
  },
  3: {
    ...mockTeacherCourseTasks[2],
    description:
      "通知学生下周课程调整安排，并同步实验课教室变更与随堂测验时间。",
    requirements: [
      "阅读通知内容并按时参加调整后的课程",
      "班委需在讨论区确认全班已知悉",
    ],
    participantCount: 68,
    submissions: [],
  },
  4: {
    ...mockTeacherCourseTasks[3],
    description:
      "通过 Wireshark 完成网络协议抓包分析实验，提交实验报告并总结 TCP、HTTP 关键字段。",
    requirements: [
      "报告需包含抓包截图与分析结论",
      "实验代码和报告一并打包上传",
      "逾期提交按课程规则扣分",
    ],
    participantCount: 68,
    averageScore: 91,
    highestScore: 99,
    lowestScore: 73,
    submissions: [
      {
        id: 1,
        studentName: "张三",
        studentId: "2021001",
        groupName: "第一组",
        status: "graded",
        submittedAt: "2024-03-19 18:35",
        score: 95,
      },
      {
        id: 2,
        studentName: "李四",
        studentId: "2021002",
        groupName: "第一组",
        status: "graded",
        submittedAt: "2024-03-19 21:10",
        score: 89,
      },
      {
        id: 3,
        studentName: "王五",
        studentId: "2021003",
        groupName: "第二组",
        status: "graded",
        submittedAt: "2024-03-20 08:42",
        score: 93,
      },
    ],
  },
};

function buildFallbackTeacherCourseTaskDetail(task: TeacherCourseTask): TeacherCourseTaskDetail {
  return {
    ...task,
    description:
      task.type === "notice"
        ? "该通知的详细内容将通过任务详情接口返回。"
        : "该任务的详细说明、提交记录和统计数据将通过任务详情接口返回。",
    requirements: [],
    participantCount: task.total,
    averageScore: task.type === "notice" ? undefined : 0,
    highestScore: task.type === "notice" ? undefined : 0,
    lowestScore: task.type === "notice" ? undefined : 0,
    submissions: [],
  };
}

const mockTeacherCourseQuestions: TeacherCourseQuestion[] = [
  {
    id: 1,
    student: "张三",
    question: "TCP三次握手的第三次可以携带数据吗?",
    confidence: "low",
    time: "10分钟前",
    status: "pending",
    replies: [],
  },
  {
    id: 2,
    student: "李四",
    question: "子网掩码255.255.255.0对应的CIDR表示是什么?",
    confidence: "low",
    time: "25分钟前",
    status: "pending",
    replies: [],
  },
  {
    id: 3,
    student: "王五",
    question: "HTTP和HTTPS的主要区别是什么?",
    confidence: "medium",
    time: "1小时前",
    status: "pending",
    replies: [],
  },
];

const mockTeacherCourseStudents: TeacherCourseStudent[] = [
  {
    id: 1,
    name: "张三",
    studentId: "2021001",
    group: 1,
    progress: 85,
    homework: 12,
    attendance: 95,
    status: "normal",
  },
  {
    id: 2,
    name: "李四",
    studentId: "2021002",
    group: 1,
    progress: 72,
    homework: 10,
    attendance: 88,
    status: "normal",
  },
  {
    id: 3,
    name: "王五",
    studentId: "2021003",
    group: 2,
    progress: 45,
    homework: 6,
    attendance: 65,
    status: "warning",
    warningReason: "作业完成率低",
  },
  {
    id: 4,
    name: "赵六",
    studentId: "2021004",
    group: 2,
    progress: 90,
    homework: 13,
    attendance: 98,
    status: "normal",
  },
  {
    id: 5,
    name: "孙七",
    studentId: "2021005",
    group: 3,
    progress: 38,
    homework: 5,
    attendance: 55,
    status: "warning",
    warningReason: "学习时长不足",
  },
  {
    id: 6,
    name: "周八",
    studentId: "2021006",
    group: 3,
    progress: 88,
    homework: 12,
    attendance: 92,
    status: "normal",
  },
  {
    id: 7,
    name: "吴九",
    studentId: "2021007",
    group: 1,
    progress: 78,
    homework: 11,
    attendance: 85,
    status: "normal",
  },
  {
    id: 8,
    name: "郑十",
    studentId: "2021008",
    group: 2,
    progress: 42,
    homework: 6,
    attendance: 60,
    status: "warning",
    warningReason: "出勤率低",
  },
];

const mockTeacherCourseHome: TeacherCourseHomeData = {
  inviteCode: "A8K9M2",
  stats: [
    {
      label: "学生总数",
      value: "68",
      sub: "已分3组",
      icon: "ri-group-line",
      iconBg: "bg-teal-50",
      iconColor: "text-teal-600",
      trend: null,
    },
    {
      label: "本周活跃",
      value: "85%",
      sub: "较上周 +3%",
      icon: "ri-line-chart-line",
      iconBg: "bg-green-50",
      iconColor: "text-green-600",
      trend: "up",
    },
    {
      label: "作业提交率",
      value: "79%",
      sub: "45/68 已提交",
      icon: "ri-file-text-line",
      iconBg: "bg-amber-50",
      iconColor: "text-amber-600",
      trend: null,
    },
    {
      label: "平均学习进度",
      value: "71%",
      sub: "较上周 +5%",
      icon: "ri-progress-3-line",
      iconBg: "bg-sky-50",
      iconColor: "text-sky-600",
      trend: "up",
    },
    {
      label: "预警学生",
      value: "3",
      sub: "需要关注",
      icon: "ri-alert-line",
      iconBg: "bg-red-50",
      iconColor: "text-red-500",
      trend: "warn",
    },
  ],
  recentTasks: [
    {
      type: "homework",
      title: "第3章课后习题",
      status: "进行中",
      statusColor: "text-teal-600 bg-teal-50",
      submitted: 45,
      total: 68,
      deadline: "03-25",
    },
    {
      type: "exam",
      title: "期中考试",
      status: "未开始",
      statusColor: "text-gray-600 bg-gray-100",
      submitted: 0,
      total: 68,
      deadline: "03-28",
    },
    {
      type: "notice",
      title: "课程调整通知",
      status: "已发布",
      statusColor: "text-green-600 bg-green-50",
      submitted: 68,
      total: 68,
      deadline: "-",
    },
    {
      type: "homework",
      title: "协议分析实验",
      status: "已结束",
      statusColor: "text-gray-500 bg-gray-100",
      submitted: 68,
      total: 68,
      deadline: "03-20",
    },
  ],
  warningStudents: [
    {
      name: "王五",
      id: "2021003",
      reason: "作业完成率低",
      progress: 45,
      attendance: 65,
      avatar: "王",
    },
    {
      name: "孙七",
      id: "2021005",
      reason: "学习时长不足",
      progress: 38,
      attendance: 55,
      avatar: "孙",
    },
    {
      name: "郑十",
      id: "2021008",
      reason: "出勤率低",
      progress: 42,
      attendance: 60,
      avatar: "郑",
    },
  ],
  activities: [
    {
      type: "submit",
      avatar: "张",
      name: "张三",
      action: "提交了作业",
      detail: "第3章课后习题",
      time: "5分钟前",
      color: "bg-green-500",
    },
    {
      type: "question",
      avatar: "李",
      name: "李四",
      action: "提出了问题",
      detail: "TCP握手可以携带数据吗",
      time: "12分钟前",
      color: "bg-amber-500",
    },
    {
      type: "submit",
      avatar: "赵",
      name: "赵六",
      action: "提交了作业",
      detail: "第3章课后习题",
      time: "18分钟前",
      color: "bg-green-500",
    },
    {
      type: "discussion",
      avatar: "吴",
      name: "吴九",
      action: "发起了讨论",
      detail: "TCP拥塞控制机制讨论",
      time: "34分钟前",
      color: "bg-teal-500",
    },
    {
      type: "progress",
      avatar: "周",
      name: "周八",
      action: "完成了章节",
      detail: "第4章 网络层",
      time: "1小时前",
      color: "bg-sky-500",
    },
    {
      type: "question",
      avatar: "王",
      name: "王五",
      action: "提出了问题",
      detail: "Dijkstra算法使用场景",
      time: "2小时前",
      color: "bg-amber-500",
    },
  ],
  weeklyStats: [
    {
      label: "新增提交",
      value: "127",
      unit: "份",
      icon: "ri-upload-2-line",
      color: "text-teal-600",
      bg: "bg-teal-50",
    },
    {
      label: "提出问题",
      value: "23",
      unit: "个",
      icon: "ri-question-line",
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
    {
      label: "讨论帖",
      value: "8",
      unit: "条",
      icon: "ri-chat-3-line",
      color: "text-sky-600",
      bg: "bg-sky-50",
    },
    {
      label: "学习时长",
      value: "4.2",
      unit: "小时均",
      icon: "ri-time-line",
      color: "text-green-600",
      bg: "bg-green-50",
    },
  ],
  groupPerformance: [
    {
      name: "第1组",
      members: 25,
      avg: 82,
      leader: "张三",
      color: "bg-teal-500",
    },
    {
      name: "第2组",
      members: 22,
      avg: 68,
      leader: "赵六",
      color: "bg-amber-400",
    },
    {
      name: "第3组",
      members: 21,
      avg: 71,
      leader: "吴九",
      color: "bg-sky-400",
    },
  ],
};

const mockCourseDiscussions: CourseDiscussion[] = [
  {
    id: 1,
    student: "赵六",
    title: "关于OSI七层模型的理解",
    content:
      "老师您好，我在学习OSI七层模型时，对于传输层和网络层的区别有些疑惑。传输层的TCP协议和网络层的IP协议在数据传输中分别起什么作用？它们之间是如何协作的？希望老师能详细讲解一下。",
    replies: [
      {
        author: "孙七",
        content: "我也有同样的疑问，期待老师解答！",
        time: "1小时前",
        isTeacher: false,
      },
      {
        author: "周八",
        content: "我觉得传输层主要负责端到端的可靠传输，网络层负责路由选择。",
        time: "50分钟前",
        isTeacher: false,
      },
    ],
    likes: 8,
    time: "2小时前",
    pinned: false,
    liked: false,
  },
  {
    id: 2,
    student: "孙七",
    title: "路由算法的实际应用场景",
    content:
      "在课堂上学习了Dijkstra算法和Bellman-Ford算法，想请教老师这两种算法在实际网络中的应用场景有什么区别？哪种算法更适合大规模网络？",
    replies: [
      {
        author: "王教授",
        content:
          "Dijkstra算法适用于边权重为正的网络，计算效率高，常用于OSPF协议。Bellman-Ford算法可以处理负权重边，但计算复杂度较高，常用于RIP协议。大规模网络通常使用Dijkstra的优化版本。",
        time: "30分钟前",
        isTeacher: true,
      },
    ],
    likes: 5,
    time: "5小时前",
    pinned: false,
    liked: false,
  },
  {
    id: 3,
    student: "吴九",
    title: "TCP拥塞控制机制讨论",
    content:
      "TCP的拥塞控制包括慢启动、拥塞避免、快重传和快恢复四个阶段。我想和大家讨论一下，在实际网络环境中，这些机制是如何协同工作的？",
    replies: [],
    likes: 3,
    time: "1天前",
    pinned: true,
    liked: false,
  },
];

const mockStudentCourseQuestions: StudentCourseQuestion[] = [
  {
    id: 1,
    title: "TCP三次握手的第三次可以携带数据吗?",
    content:
      "老师您好，我在学习TCP协议时，看到资料说第三次握手可以携带数据，但不太理解为什么前两次不能携带数据。能否详细解释一下原因？",
    time: "2024-03-18 10:30",
    status: "answered",
    replies: [
      {
        author: "王教授",
        content:
          "是的，TCP三次握手的第三次握手可以携带数据。\n\n原因如下：\n• 第一次握手（SYN）：客户端发送SYN报文，此时连接尚未建立，不能携带数据\n• 第二次握手（SYN+ACK）：服务器回复SYN+ACK报文，连接仍未完全建立，不能携带数据\n• 第三次握手（ACK）：客户端发送ACK报文，此时连接已建立，可以携带数据\n\n这是因为前两次握手时连接尚未完全建立，而第三次握手时客户端已经确认服务器的接收能力，连接进入ESTABLISHED状态，因此可以开始传输应用层数据。",
        time: "2024-03-18 14:20",
        isTeacher: true,
      },
    ],
  },
  {
    id: 2,
    title: "红黑树的左旋和右旋操作具体是如何实现的?",
    content: "在学习红黑树时，对左旋和右旋操作的具体实现不太理解，能否提供一个详细的图解或代码示例？",
    time: "2024-03-17 15:45",
    status: "pending",
    replies: [],
  },
  {
    id: 3,
    title: "HTTP和HTTPS的主要区别是什么?",
    content: "除了加密之外，HTTP和HTTPS在性能、端口等方面还有哪些区别？",
    time: "2024-03-16 09:20",
    status: "answered",
    replies: [
      {
        author: "王教授",
        content:
          "HTTP与HTTPS的主要区别包括：\n\n1. 安全性：HTTP是明文传输，HTTPS通过TLS/SSL加密传输\n2. 端口：HTTP默认使用80端口，HTTPS默认使用443端口\n3. 证书：HTTPS需要CA颁发的数字证书\n4. 性能：HTTPS因加密解密有轻微性能开销\n5. SEO：搜索引擎对HTTPS站点有更高的排名权重",
        time: "2024-03-16 16:30",
        isTeacher: true,
      },
    ],
  },
];

const mockStudentCourseDiscussions: CourseDiscussion[] = [
  {
    id: 1,
    student: "张三",
    title: "关于OSI七层模型的理解",
    content:
      "老师您好，我在学习OSI七层模型时，对于传输层和网络层的区别有些疑惑。传输层的TCP协议和网络层的IP协议在数据传输中分别起什么作用？它们之间是如何协作的？希望老师能详细讲解一下。",
    replies: [
      {
        author: "李四",
        content: "我也有同样的疑问，期待老师解答！",
        time: "1小时前",
        isStudent: true,
      },
      {
        author: "王五",
        content: "我觉得传输层主要负责端到端的可靠传输，网络层负责路由选择。",
        time: "50分钟前",
        isStudent: true,
      },
    ],
    likes: 8,
    time: "2小时前",
    liked: false,
  },
  {
    id: 2,
    student: "李四",
    title: "路由算法的实际应用场景",
    content: "在课堂上学习了Dijkstra算法和Bellman-Ford算法，想请教老师这两种算法在实际网络中的应用场景有什么区别？哪种算法更适合大规模网络？",
    replies: [],
    likes: 5,
    time: "5小时前",
    liked: false,
  },
  {
    id: 3,
    student: "王五",
    title: "TCP拥塞控制机制讨论",
    content: "TCP的拥塞控制包括慢启动、拥塞避免、快重传和快恢复四个阶段。我想和大家讨论一下，在实际网络环境中，这些机制是如何协同工作的？",
    replies: [
      {
        author: "赵六",
        content: "我认为慢启动阶段是指数增长，拥塞避免是线性增长，这样可以快速探测网络容量同时避免过度拥塞。",
        time: "3小时前",
        isStudent: true,
      },
    ],
    likes: 3,
    time: "1天前",
    liked: false,
  },
];

const mockCourseFaqs: CourseFaq[] = [
  {
    id: 1,
    title: "第5章高频问题解答",
    date: "2024-03-10",
    views: 156,
    content:
      "本次集中答疑主要针对第5章传输层的高频问题进行解答：\n\n1. TCP三次握手和四次挥手的详细过程\n2. TCP拥塞控制算法的工作原理\n3. UDP协议的应用场景\n4. 滑动窗口机制的实现细节\n\n详细内容请查看附件文档。",
    attachments: ["第5章答疑汇总.pdf"],
  },
  {
    id: 2,
    title: "TCP协议常见疑问",
    date: "2024-03-05",
    views: 142,
    content:
      "针对同学们在学习TCP协议时遇到的常见问题进行统一解答：\n\n1. 为什么需要三次握手？两次不行吗？\n2. TIME_WAIT状态的作用是什么？\n3. TCP如何保证可靠传输？\n4. 粘包问题如何解决？",
    attachments: [],
  },
  {
    id: 3,
    title: "期中考试答疑汇总",
    date: "2024-02-28",
    views: 189,
    content:
      "期中考试前的集中答疑内容汇总，包括：\n\n1. 各层协议的主要功能\n2. 常见网络设备的工作层次\n3. 子网划分的计算方法\n4. 路由算法的比较",
    attachments: ["期中考试复习要点.pdf", "历年真题解析.pdf"],
  },
];

const mockStudentCourseTasks: StudentCourseTask[] = [
  {
    id: "hw-tree-binary",
    title: "第5章树与二叉树课后作业",
    deadline: "今天 23:59",
    status: "pending",
    score: null,
    urgent: true,
    questions: [
      { id: 1, content: "请简述二叉树的三种遍历方式（前序、中序、后序）的区别。", type: "text", answer: "" },
      { id: 2, content: "什么是完全二叉树？请画图说明。", type: "text", answer: "" },
      { id: 3, content: "红黑树的五个性质是什么？", type: "text", answer: "" },
    ],
  },
  {
    id: "hw-graph",
    title: "第4章图论算法实现",
    deadline: "明天 23:59",
    status: "pending",
    score: null,
    urgent: false,
    questions: [
      { id: 1, content: "请用代码实现图的深度优先遍历（DFS）。", type: "code", answer: "" },
      { id: 2, content: "请用代码实现图的广度优先遍历（BFS）。", type: "code", answer: "" },
    ],
  },
  {
    id: "exam-midterm-os",
    title: "操作系统期中考试",
    startTime: "明天 14:00",
    deadline: "明天 16:00",
    duration: 90,
    status: "pending",
    score: null,
    urgent: false,
    isExam: true,
    questions: [
      { id: 1, content: "请简述进程与线程的区别，并说明在什么场景下优先选择多线程而非多进程。", type: "text", answer: "" },
      { id: 2, content: "操作系统的四种进程调度算法各有什么优缺点？请结合实际场景分析。", type: "text", answer: "" },
      { id: 3, content: "什么是死锁？产生死锁的四个必要条件是什么？请给出一种预防死锁的方法。", type: "text", answer: "" },
      { id: 4, content: "请说明页面置换算法（FIFO、LRU、OPT）的工作原理，并比较其优劣。", type: "text", answer: "" },
    ],
  },
  {
    id: "hw-stack-queue",
    title: "第3章栈和队列练习",
    deadline: "2024-03-15",
    status: "submitted",
    score: null,
    urgent: false,
    questions: [],
  },
  {
    id: "hw-linear-list",
    title: "第2章线性表编程题",
    deadline: "2024-03-10",
    status: "graded",
    score: 88,
    urgent: false,
    questions: [
      { id: 1, content: "请实现单链表的插入操作。", type: "code", answer: "function insert(head, value) { ... }", correct: true, comment: "实现正确，代码规范" },
      { id: 2, content: "请实现单链表的删除操作。", type: "code", answer: "function delete(head, value) { ... }", correct: false, comment: "边界条件处理不完善，需要考虑删除头节点的情况" },
      { id: 3, content: "请实现单链表的反转操作。", type: "code", answer: "function reverse(head) { ... }", correct: true, comment: "实现正确，思路清晰" },
    ],
    teacherComment: "整体完成较好，但需要注意边界条件的处理。建议多做一些链表相关的练习题。",
  },
  {
    id: "hw-complexity",
    title: "第1章算法复杂度分析",
    deadline: "2024-03-05",
    status: "graded",
    score: 95,
    urgent: false,
    questions: [
      { id: 1, content: "请分析冒泡排序的时间复杂度。", type: "text", answer: "O(n^2)", correct: true, comment: "分析正确" },
      { id: 2, content: "请分析快速排序的平均时间复杂度。", type: "text", answer: "O(nlogn)", correct: true, comment: "分析正确" },
    ],
    teacherComment: "非常好！对算法复杂度的理解很到位。",
  },
];

const mockStudentCourseHome: StudentCourseHomeData = {
  welcome: {
    studentName: "李浩然",
    weeklyStudyHours: "18.5小时",
    weeklyGoalRemaining: "1.5小时",
    courseProgress: 75,
    streakDays: 30,
    homeworkCompleted: "12/15",
    learnedChapters: "28/32",
    aiQuestions: "47次",
  },
  quickActions: [
    {
      icon: "ri-folder-open-line",
      label: "课程资料",
      sub: "7份文件",
      color: "from-teal-50 to-teal-100",
      iconColor: "text-teal-600",
      section: "materials",
    },
    {
      icon: "ri-task-line",
      label: "待做作业",
      sub: "3项截止",
      color: "from-orange-50 to-orange-100",
      iconColor: "text-orange-600",
      section: "tasks",
    },
    {
      icon: "ri-robot-line",
      label: "AI助教",
      sub: "随时提问",
      color: "from-sky-50 to-sky-100",
      iconColor: "text-sky-600",
      section: "ai",
    },
    {
      icon: "ri-stack-line",
      label: "学习闪卡",
      sub: "12张待复习",
      color: "from-violet-50 to-violet-100",
      iconColor: "text-violet-600",
      section: "flashcards",
    },
  ],
  notices: [
    {
      title: "期中考试安排通知",
      content: "期中考试将于4月15日（周三）14:00在三教301进行，请携带学生证入场，禁止携带电子设备。",
      time: "2小时前",
      important: true,
      tag: "重要",
    },
    {
      title: "第6章应用层学习资料已上传",
      content: "HTTP协议、DNS解析、FTP等应用层协议讲义已上传至课程资料，请同学们提前预习。",
      time: "1天前",
      important: false,
      tag: "资料",
    },
    {
      title: "本周五下午集中答疑",
      content: "周五14:00-16:00在工学部实验室A203进行集中答疑，主要针对TCP/UDP章节的疑问。",
      time: "2天前",
      important: false,
      tag: "答疑",
    },
    {
      title: "第5章作业成绩已公布",
      content: "第5章传输层作业已批改完毕，平均分82分，请登录任务中心查看详细评语。",
      time: "3天前",
      important: false,
      tag: "成绩",
    },
  ],
  upcomingTasks: [
    {
      title: "第5章树与二叉树作业",
      deadline: "今天 23:59",
      urgent: true,
      icon: "ri-file-list-3-line",
    },
    {
      title: "操作系统期中考试",
      deadline: "明天 14:00",
      urgent: true,
      icon: "ri-file-edit-line",
    },
    {
      title: "第4章图论算法实现",
      deadline: "明天 23:59",
      urgent: false,
      icon: "ri-code-s-slash-line",
    },
  ],
  todayUpdates: [
    {
      type: "pdf",
      title: "第6章应用层.pdf",
      time: "2h前",
      color: "bg-red-50 text-red-600",
      icon: "ri-file-pdf-line",
    },
    {
      type: "video",
      title: "TCP拥塞控制讲解.mp4",
      time: "1天前",
      color: "bg-violet-50 text-violet-600",
      icon: "ri-video-line",
    },
    {
      type: "hw",
      title: "第5章作业批改结果",
      time: "1天前",
      color: "bg-green-50 text-green-600",
      icon: "ri-checkbox-circle-line",
    },
  ],
  classActivities: [
    {
      name: "赵一鸣",
      avatar: "赵",
      action: "完成了第5章课后作业",
      detail: "得分 96 分",
      time: "10分钟前",
      avatarBg: "from-teal-400 to-cyan-500",
      icon: "ri-checkbox-circle-line",
      iconColor: "text-green-500",
    },
    {
      name: "陈明阳",
      avatar: "陈",
      action: "提问了 TCP 三次握手原理",
      detail: "AI已回复",
      time: "32分钟前",
      avatarBg: "from-orange-400 to-amber-500",
      icon: "ri-chat-3-line",
      iconColor: "text-sky-500",
    },
    {
      name: "孙晓雪",
      avatar: "孙",
      action: "创建了新的学习闪卡组",
      detail: "第6章 · 28张",
      time: "1小时前",
      avatarBg: "from-violet-400 to-purple-500",
      icon: "ri-stack-line",
      iconColor: "text-violet-500",
    },
    {
      name: "刘宇轩",
      avatar: "刘",
      action: "完成了今日复习任务",
      detail: "复习 15 张",
      time: "2小时前",
      avatarBg: "from-green-400 to-emerald-500",
      icon: "ri-refresh-line",
      iconColor: "text-teal-500",
    },
    {
      name: "周静怡",
      avatar: "周",
      action: "参与了班级讨论",
      detail: "关于路由算法",
      time: "3小时前",
      avatarBg: "from-pink-400 to-rose-500",
      icon: "ri-discuss-line",
      iconColor: "text-orange-500",
    },
  ],
  milestones: [
    { title: "第1-3章学习", date: "已完成", done: true, current: false },
    { title: "期中考试", date: "4月15日", done: false, current: true, urgent: true },
    { title: "第4-6章学习", date: "进行中", done: false, current: true },
    { title: "综合实验报告", date: "5月10日", done: false, current: false },
    { title: "期末考试", date: "6月22日", done: false, current: false },
  ],
  progress: {
    percent: 75,
    startDate: "2026/02/28",
    endDate: "2026/06/30",
  },
};

export function getMockCourseKnowledgeGraph(
  courseId: string,
): KnowledgeGraphData {
  const course = courseMap[courseId as keyof typeof courseMap];

  return {
    nodes: mockKnowledgeGraphNodes.map((node) =>
      node.id === "root" && course ? { ...node, label: course.name } : { ...node },
    ),
    edges: mockKnowledgeGraphEdges.map((edge) => ({ ...edge })),
    meta: {
      rootNodeId: "root",
      layout: "preset",
    },
  };
}

export function getMockStudentCourseMaterials(): StudentCourseMaterialsData {
  return {
    files: mockStudentCourseMaterials.map((file) => ({ ...file })),
  };
}

export function getMockTeacherCourseMaterials(): TeacherCourseMaterialsData {
  return {
    files: mockTeacherCourseFiles.map((file) => ({ ...file })),
  };
}

export function getMockTeacherCourseMaterialPreview(
  fileId: number,
): TeacherCourseMaterialPreviewData {
  const detail =
    mockTeacherCourseMaterialPreviews[fileId] ??
    buildFallbackTeacherCourseMaterialPreview(
      mockTeacherCourseFiles.find((file) => file.id === fileId) ?? mockTeacherCourseFiles[0],
    );

  return {
    ...detail,
  };
}

export function getMockTeacherCourseMaterialDownload(
  fileId: number,
): TeacherCourseMaterialDownloadData {
  const file =
    mockTeacherCourseFiles.find((item) => item.id === fileId) ?? mockTeacherCourseFiles[0];
  const downloadContent = `Mock download: ${file.name}\nThis file simulates a backend download URL for frontend integration.`;

  return {
    fileId: file.id,
    fileName: file.name,
    downloadUrl: `data:text/plain;charset=utf-8,${encodeURIComponent(downloadContent)}`,
  };
}

export function getMockTeacherCourseMaterialAnalysis(
  fileId: number,
): TeacherCourseMaterialAnalysisDetail {
  const detail =
    mockTeacherCourseMaterialAnalyses[fileId] ??
    buildFallbackTeacherCourseMaterialAnalysis(
      mockTeacherCourseFiles.find((file) => file.id === fileId) ?? mockTeacherCourseFiles[0],
    );

  return {
    ...detail,
    keyPoints: [...detail.keyPoints],
    difficulties: detail.difficulties.map((item) => ({ ...item })),
  };
}

export function getMockTeacherCourseTasks(): TeacherCourseTasksData {
  return {
    tasks: mockTeacherCourseTasks.map((task) => ({
      ...task,
      attachments: [...task.attachments],
    })),
  };
}

export function getMockTeacherCourseTaskDetail(taskId: number): TeacherCourseTaskDetail {
  const detail =
    mockTeacherCourseTaskDetails[taskId] ??
    buildFallbackTeacherCourseTaskDetail(
      mockTeacherCourseTasks.find((task) => task.id === taskId) ?? mockTeacherCourseTasks[0],
    );

  return {
    ...detail,
    attachments: [...detail.attachments],
    requirements: [...detail.requirements],
    submissions: detail.submissions.map((submission) => ({ ...submission })),
  };
}

export function getMockTeacherCourseQuestions(): TeacherCourseQuestionsData {
  return {
    questions: mockTeacherCourseQuestions.map((question) => ({
      ...question,
      replies: question.replies.map((reply) => ({ ...reply })),
    })),
  };
}

export function getMockTeacherCourseStudents(): TeacherCourseStudentsData {
  return {
    students: mockTeacherCourseStudents.map((student) => ({ ...student })),
  };
}

export function getMockTeacherCourseHome(): TeacherCourseHomeData {
  return {
    inviteCode: mockTeacherCourseHome.inviteCode,
    stats: mockTeacherCourseHome.stats.map((item) => ({ ...item })),
    recentTasks: mockTeacherCourseHome.recentTasks.map((item) => ({ ...item })),
    warningStudents: mockTeacherCourseHome.warningStudents.map((item) => ({
      ...item,
    })),
    activities: mockTeacherCourseHome.activities.map((item) => ({ ...item })),
    weeklyStats: mockTeacherCourseHome.weeklyStats.map((item) => ({ ...item })),
    groupPerformance: mockTeacherCourseHome.groupPerformance.map((item) => ({
      ...item,
    })),
  };
}

export function getMockCourseDiscussions(): CourseDiscussionsData {
  return {
    discussions: mockCourseDiscussions.map((discussion) => ({
      ...discussion,
      replies: discussion.replies.map((reply) => ({ ...reply })),
    })),
  };
}

export function getMockStudentCourseQuestions(): StudentCourseQuestionsData {
  return {
    questions: mockStudentCourseQuestions.map((question) => ({
      ...question,
      replies: question.replies.map((reply) => ({ ...reply })),
    })),
  };
}

export function getMockStudentCourseDiscussions(): CourseDiscussionsData {
  return {
    discussions: mockStudentCourseDiscussions.map((discussion) => ({
      ...discussion,
      replies: discussion.replies.map((reply) => ({ ...reply })),
    })),
  };
}

export function getMockCourseFaqs(): CourseFaqsData {
  return {
    faqs: mockCourseFaqs.map((faq) => ({
      ...faq,
      attachments: [...faq.attachments],
    })),
  };
}

export function getMockStudentCourseTasks(): StudentCourseTasksData {
  return {
    tasks: mockStudentCourseTasks.map((task) => ({
      ...task,
      questions: task.questions.map((question) => ({ ...question })),
    })),
  };
}

export function getMockStudentCourseHome(): StudentCourseHomeData {
  return {
    welcome: { ...mockStudentCourseHome.welcome },
    quickActions: mockStudentCourseHome.quickActions.map((item) => ({ ...item })),
    notices: mockStudentCourseHome.notices.map((notice) => ({ ...notice })),
    upcomingTasks: mockStudentCourseHome.upcomingTasks.map((task) => ({ ...task })),
    todayUpdates: mockStudentCourseHome.todayUpdates.map((item) => ({ ...item })),
    classActivities: mockStudentCourseHome.classActivities.map((item) => ({
      ...item,
    })),
    milestones: mockStudentCourseHome.milestones.map((item) => ({ ...item })),
    progress: { ...mockStudentCourseHome.progress },
  };
}

export function getMockStudentCourseBootstrap(
  courseId: string,
): StudentCourseBootstrapData {
  return {
    course: courseMap[courseId as keyof typeof courseMap] || {
      id: courseId,
      name: "未知课程",
      teacher: "未知教师",
      code: "UNKNOWN",
    },
    defaultSection: "home",
    enrolledAt: "2024-02-26",
    completionRate: courseId === "1" ? 68 : 52,
    unreadCount: courseId === "1" ? 2 : 0,
  };
}

export function getMockTeacherCourseBootstrap(
  courseId: string,
): TeacherCourseBootstrapData {
  return {
    course: courseMap[courseId as keyof typeof courseMap] || {
      id: courseId,
      name: "未知课程",
      teacher: "未知教师",
      code: "UNKNOWN",
    },
    defaultSection: "home",
    inviteCode: mockTeacherCourseHome.inviteCode,
    studentCount: 68,
    materialCount: mockTeacherCourseFiles.length,
    pendingQuestionCount: mockTeacherCourseQuestions.filter(
      (question) => question.status === "pending",
    ).length,
  };
}

function createInviteCode(seed = "") {
  const normalized = seed.replace(/[^a-z0-9]/gi, "").toUpperCase();
  return (normalized || Math.random().toString(36).slice(2, 8))
    .padEnd(6, "X")
    .slice(0, 6);
}

export function mockJoinCourse(payload: JoinCourseRequest): JoinCourseResult {
  return {
    course: {
      id: payload.inviteCode.toLowerCase(),
      name: "新加入课程",
      teacher: "待同步教师",
      code: payload.inviteCode.toUpperCase(),
    },
  };
}

export function mockCreateCourse(
  payload: CreateCourseRequest,
): CreateCourseResult {
  const courseId = payload.code || Date.now().toString();

  return {
    course: {
      id: courseId,
      name: payload.name,
      teacher: "当前教师",
      code: payload.code,
    },
    inviteCode: createInviteCode(payload.code || payload.name),
  };
}

export function mockGenerateInviteCode(
  courseId: string,
): GenerateInviteCodeResult {
  return {
    courseId,
    inviteCode: createInviteCode(courseId),
  };
}
