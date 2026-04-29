import { useState, useRef, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import KnowledgeGraphViewer from '@/components/KnowledgeGraphViewer';
import TeacherAIAssistant from './components/TeacherAIAssistant';
import {
  getKnowledgeGraphRootIds,
  normalizeKnowledgeGraph,
} from '@/lib/knowledge-graph';
import { useCourseBootstrap } from '@/lib/use-course-bootstrap';
import { aiService } from '@/services/ai';
import { courseService } from '@/services/course';
import type {
  CourseDiscussion,
  KnowledgeGraphEdge,
  KnowledgeGraphNode,
  TeacherCourseFile,
  TeacherCourseHomeData,
  TeacherCourseMaterialAnalysisDetail,
  TeacherCourseMaterialPreviewData,
  TeacherCourseQuestion,
  TeacherCourseStudent,
  TeacherCourseTaskDetail,
  TeacherCourseTask,
} from '@/types/course';
import type { AiTeacherQuestion } from '@/types/ai';

const EMPTY_TEACHER_HOME: TeacherCourseHomeData = {
  inviteCode: '',
  stats: [],
  recentTasks: [],
  warningStudents: [],
  activities: [],
  weeklyStats: [],
  groupPerformance: [],
};

function createEmptyNoticeForm() {
  return {
    title: '',
    content: '',
    importance: 'normal',
    scope: 'all',
    attachments: [] as File[],
  };
}

function createEmptyHomeworkQuestion() {
  return {
    description: '',
    answer: '',
  };
}

function createEmptyHomeworkForm() {
  return {
    title: '',
    deadline: '',
    allowLate: false,
    questions: [createEmptyHomeworkQuestion()],
    attachments: [] as File[],
  };
}

function createEmptyExamForm() {
  return {
    name: '',
    startTime: '',
    endTime: '',
    duration: 90,
    totalScore: 100,
    questionCount: 10,
    generatedQuestions: [] as { type: string; content: string; score: number }[],
    attachments: [] as File[],
  };
}

function createEmptyExportForm() {
  return {
    scope: 'current',
    format: 'csv',
    fields: {
      name: true,
      studentId: true,
      group: true,
      progress: true,
      homework: true,
      attendance: true,
    },
  };
}

function createEmptyDiscussionForm() {
  return {
    title: '',
    content: '',
    pinned: false,
  };
}

interface Message {
  id: number;
  role: 'user' | 'ai';
  content: string;
  time: string;
  sources?: { name: string; page: number; type: string }[];
}

type CourseFileId = TeacherCourseFile['id'];

const AI_RESPONSES: Record<string, { content: string; sources?: { name: string; page: number; type: string }[] }> = {
  default: {
    content: '这是一个很好的问题！根据课程知识库中的内容，我来为您详细解答。\n\n计算机网络是现代信息技术的基础，涵盖了从物理层到应用层的多个协议栈层次。如需了解具体某个知识点，欢迎继续提问。',
    sources: [{ name: '第1章-计算机网络概述.pdf', page: 3, type: 'pdf' }],
  },
  tcp: {
    content: 'TCP三次握手过程如下：\n\n**第一次握手**：客户端发送SYN报文（SYN=1, seq=x），进入SYN_SENT状态。\n\n**第二次握手**：服务器收到后回复SYN+ACK报文（SYN=1, ACK=1, seq=y, ack=x+1），进入SYN_RCVD状态。\n\n**第三次握手**：客户端发送ACK报文（ACK=1, seq=x+1, ack=y+1），双方进入ESTABLISHED状态。\n\n第三次握手**可以携带数据**，但前两次不能携带数据。',
    sources: [
      { name: '第4章-传输层.pdf', page: 12, type: 'pdf' },
      { name: 'TCP协议详解视频.mp4', page: 0, type: 'video' },
    ],
  },
  http: {
    content: 'HTTP与HTTPS的主要区别：\n\n1. **安全性**：HTTP是明文传输，HTTPS通过TLS/SSL加密传输，防止数据被窃听和篡改。\n\n2. **端口**：HTTP默认使用80端口，HTTPS默认使用443端口。\n\n3. **证书**：HTTPS需要CA颁发的数字证书，用于身份验证。\n\n4. **性能**：HTTPS因加密解密有轻微性能开销，但现代硬件影响极小。\n\n5. **SEO**：搜索引擎对HTTPS站点有更高的排名权重。',
    sources: [{ name: '第5章-应用层.pdf', page: 8, type: 'pdf' }],
  },
  subnet: {
    content: '子网掩码255.255.255.0的CIDR表示为 **/24**。\n\n原因：255.255.255.0转换为二进制是24个连续的1，即：\n`11111111.11111111.11111111.00000000`\n\n因此CIDR前缀长度为24，写作 `/24`。\n\n例如：192.168.1.0/24 表示该网络有256个地址（192.168.1.0 ~ 192.168.1.255），其中可用主机地址254个。',
    sources: [{ name: '第3章-网络层.pdf', page: 15, type: 'pdf' }],
  },
};

function getAIResponse(input: string) {
  const lower = input.toLowerCase();
  if (lower.includes('tcp') || lower.includes('握手')) return AI_RESPONSES.tcp;
  if (lower.includes('http') || lower.includes('https')) return AI_RESPONSES.http;
  if (lower.includes('子网') || lower.includes('255') || lower.includes('cidr')) return AI_RESPONSES.subnet;
  return AI_RESPONSES.default;
}

function TeacherCourseEmptyState({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center text-gray-500">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-50 text-gray-400">
        <i className={`${icon} text-2xl`}></i>
      </div>
      <div className="text-sm font-medium text-gray-700">{title}</div>
      <div className="mt-1 max-w-sm text-xs leading-5 text-gray-400">{description}</div>
    </div>
  );
}

function buildTaskDetailFallback(task: TeacherCourseTask): TeacherCourseTaskDetail {
  return {
    ...task,
    description:
      task.type === 'notice'
        ? '该通知的详细内容将在任务详情接口接入后返回，这里先展示列表中的基础信息。'
        : '该任务的详细说明、提交记录和统计数据将在任务详情接口接入后返回，这里先展示列表中的基础信息。',
    requirements: [],
    participantCount: task.total,
    averageScore: task.type === 'notice' ? undefined : 0,
    highestScore: task.type === 'notice' ? undefined : 0,
    lowestScore: task.type === 'notice' ? undefined : 0,
    submissions: [],
  };
}

function getTaskSubmissionStatusMeta(status: 'submitted' | 'pending' | 'graded') {
  if (status === 'graded') {
    return {
      label: '已批改',
      className: 'bg-green-50 text-green-600',
    };
  }

  if (status === 'submitted') {
    return {
      label: '已提交',
      className: 'bg-blue-50 text-blue-600',
    };
  }

  return {
    label: '未提交',
    className: 'bg-gray-100 text-gray-600',
  };
}

function isIndexedMaterialStatus(status: string) {
  const normalized = status.trim().toLowerCase();
  return ['indexed', 'completed', 'complete', 'success', 'ready', '已解析', '解析完成'].includes(normalized);
}

function getMaterialStatusMeta(status: string) {
  const normalized = status.trim().toLowerCase();

  if (isIndexedMaterialStatus(status)) {
    return {
      label: '已解析',
      className: 'bg-green-50 text-green-600',
    };
  }

  if (['failed', 'error', '解析失败'].includes(normalized)) {
    return {
      label: '解析失败',
      className: 'bg-red-50 text-red-600',
    };
  }

  if (['partial', 'degraded', '部分完成'].includes(normalized)) {
    return {
      label: '部分完成',
      className: 'bg-orange-50 text-orange-600',
    };
  }

  if (['pending', 'queued', 'processing', 'running', '待解析', '解析中'].includes(normalized)) {
    return {
      label: '解析中',
      className: 'bg-yellow-50 text-yellow-600',
    };
  }

  return {
    label: status || '待解析',
    className: 'bg-gray-100 text-gray-600',
  };
}

function buildMaterialAnalysisFallback(
  file: TeacherCourseFile,
): TeacherCourseMaterialAnalysisDetail {
  return {
    fileId: file.id,
    summary: `${file.name} 的 AI 解析结果将在资料解析接口接入后返回，这里先保留后端联调所需的数据结构。`,
    keyPoints: ['资料主题识别', '核心知识点提取', '学习难点分析'],
    difficulties: [{ title: '等待后端返回具体难点', difficulty: '中等' }],
    recommendedStudyDuration: '待分析',
    generatedAt: file.date,
  };
}

function buildMaterialPreviewFallback(
  file: TeacherCourseFile,
): TeacherCourseMaterialPreviewData {
  return {
    fileId: file.id,
    previewType:
      file.type === 'Video'
        ? 'video'
        : file.type === 'PPT'
          ? 'slide'
          : 'document',
    previewUrl: '',
    note: `${file.name} 的预览地址将在联调接口接入后返回，这里先保留预览结构。`,
  };
}

function buildAiAnswerFallback(question: TeacherCourseQuestion): AiTeacherQuestion {
  return {
    id: question.id,
    student: question.student,
    avatar: question.student[0] ?? '学',
    question: question.question,
    aiAnswer: '该问题的 AI 回答详情将在联调接口接入后返回，这里先保留弹窗结构和基础兜底文案。',
    confidence: question.confidence === 'medium' ? 60 : 35,
    confidenceLevel: question.confidence === 'medium' ? 'medium' : 'low',
    sources: [],
    time: question.time,
    status: 'pending',
  };
}

export default function TeacherCourse() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [activeSection, setActiveSection] = useState('home');
  const { bootstrap, course, courseError } = useCourseBootstrap(id, 'teacher');
  const courseId = course?.id ?? id ?? '1';

  useEffect(() => {
    const section = searchParams.get('section');
    if (section && ['home', 'knowledge', 'tasks', 'interaction', 'students', 'ai'].includes(section)) {
      setActiveSection(section);
    }
  }, [searchParams]);
  const [teacherHome, setTeacherHome] = useState<TeacherCourseHomeData>(EMPTY_TEACHER_HOME);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [graphNodes, setGraphNodes] = useState<KnowledgeGraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<KnowledgeGraphEdge[]>([]);
  const [graphRootIds, setGraphRootIds] = useState<string[]>(['root']);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 新增：课程资料相关状态
  const [expandedFiles, setExpandedFiles] = useState<CourseFileId[]>([]);
  const [showFileMenu, setShowFileMenu] = useState<CourseFileId | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [showAIAnalysisModal, setShowAIAnalysisModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [currentFile, setCurrentFile] = useState<TeacherCourseFile | null>(null);
  const [currentFilePreview, setCurrentFilePreview] = useState<TeacherCourseMaterialPreviewData | null>(null);
  const [isFilePreviewLoading, setIsFilePreviewLoading] = useState(false);
  const [filePreviewError, setFilePreviewError] = useState('');
  const [currentFileAnalysis, setCurrentFileAnalysis] = useState<TeacherCourseMaterialAnalysisDetail | null>(null);
  const [isFileAnalysisLoading, setIsFileAnalysisLoading] = useState(false);
  const [fileAnalysisError, setFileAnalysisError] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const [fileFilter, setFileFilter] = useState('all');
  const [fileSortBy, setFileSortBy] = useState('date');
  const [courseFiles, setCourseFiles] = useState<TeacherCourseFile[]>([]);
  const [downloadingFileId, setDownloadingFileId] = useState<CourseFileId | null>(null);

  // 新增：任务发布相关状态
  const [showNoticeModal, setShowNoticeModal] = useState(false);
  const [showHomeworkModal, setShowHomeworkModal] = useState(false);
  const [showExamModal, setShowExamModal] = useState(false);
  const [noticeForm, setNoticeForm] = useState(createEmptyNoticeForm);
  const [homeworkForm, setHomeworkForm] = useState(createEmptyHomeworkForm);
  const [examForm, setExamForm] = useState(createEmptyExamForm);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false);
  const noticeAttachmentRef = useRef<HTMLInputElement>(null);
  const homeworkAttachmentRef = useRef<HTMLInputElement>(null);
  const examAttachmentRef = useRef<HTMLInputElement>(null);

  // 新增：已发布任务相关状态
  const [taskFilter, setTaskFilter] = useState('all');
  const [showTaskDetailModal, setShowTaskDetailModal] = useState(false);
  const [currentTask, setCurrentTask] = useState<TeacherCourseTaskDetail | null>(null);
  const [isTaskDetailLoading, setIsTaskDetailLoading] = useState(false);
  const [taskDetailError, setTaskDetailError] = useState('');
  const [publishedTasks, setPublishedTasks] = useState<TeacherCourseTask[]>([]);

  // 新增：互动空间相关状态
  const [expandedQuestions, setExpandedQuestions] = useState<number[]>([]);
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyContent, setReplyContent] = useState('');
  const [showAIAnswerModal, setShowAIAnswerModal] = useState(false);
  const [currentAIAnswer, setCurrentAIAnswer] = useState<AiTeacherQuestion | null>(null);
  const [isAIAnswerLoading, setIsAIAnswerLoading] = useState(false);
  const [aiAnswerError, setAiAnswerError] = useState('');
  const [questions, setQuestions] = useState<TeacherCourseQuestion[]>([]);

  // 新增：学生管理相关状态
  const [studentGroupTab, setStudentGroupTab] = useState('all');
  const [studentSearchQuery, setStudentSearchQuery] = useState('');
  const [showGroupManageModal, setShowGroupManageModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportForm, setExportForm] = useState(createEmptyExportForm);
  const [students, setStudents] = useState<TeacherCourseStudent[]>([]);
  const [selectedStudents, setSelectedStudents] = useState<number[]>([]);
  const [targetGroup, setTargetGroup] = useState<number>(1);

  // 新增：班级讨论相关状态
  const [expandedDiscussions, setExpandedDiscussions] = useState<number[]>([]);
  const [replyingToDiscussion, setReplyingToDiscussion] = useState<number | null>(null);
  const [discussionReplyContent, setDiscussionReplyContent] = useState('');
  const [showNewDiscussionModal, setShowNewDiscussionModal] = useState(false);
  const [newDiscussionForm, setNewDiscussionForm] = useState(createEmptyDiscussionForm);
  const [discussions, setDiscussions] = useState<CourseDiscussion[]>([]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    setUploadFiles(prev => [...prev, ...files]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setUploadFiles(prev => [...prev, ...files]);
    }
  };

  const removeFile = (index: number) => {
    setUploadFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') return { icon: 'ri-file-pdf-line', color: 'text-red-600', bg: 'bg-red-50' };
    if (ext === 'pptx' || ext === 'ppt') return { icon: 'ri-file-ppt-line', color: 'text-orange-600', bg: 'bg-orange-50' };
    if (ext === 'mp4' || ext === 'avi' || ext === 'mov') return { icon: 'ri-video-line', color: 'text-purple-600', bg: 'bg-purple-50' };
    if (ext === 'docx' || ext === 'doc') return { icon: 'ri-file-word-line', color: 'text-blue-600', bg: 'bg-blue-50' };
    return { icon: 'ri-file-line', color: 'text-gray-600', bg: 'bg-gray-50' };
  };

  const refreshKnowledgeData = async () => {
    const [materials, graph] = await Promise.all([
      courseService.getTeacherCourseMaterials(courseId),
      courseService.getKnowledgeGraph(courseId, 'teacher'),
    ]);

    const normalized = normalizeKnowledgeGraph(graph);
    const rootIds = getKnowledgeGraphRootIds(normalized);

    setCourseFiles(materials.files);
    setGraphNodes(normalized.nodes);
    setGraphEdges(normalized.edges);
    setGraphRootIds(rootIds);
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setIsUploading(true);
    
    for (const file of uploadFiles) {
      const fileName = file.name;
      setUploadProgress(prev => ({ ...prev, [fileName]: 0 }));
      
      // 模拟上传进度
      for (let i = 0; i <= 100; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 100));
        setUploadProgress(prev => ({ ...prev, [fileName]: i }));
      }
    }
    
    await courseService.uploadTeacherCourseFiles(courseId, uploadFiles);
    await refreshKnowledgeData();
    await new Promise(resolve => setTimeout(resolve, 500));
    setIsUploading(false);
    setUploadFiles([]);
    setUploadProgress({});
    setShowUploadModal(false);
    alert('资料上传成功！');
  };

  useEffect(() => {
    let mounted = true;

    courseService
      .getKnowledgeGraph(courseId, 'teacher')
      .then((data) => {
        if (!mounted) return;
        const normalized = normalizeKnowledgeGraph(data);
        const rootIds = getKnowledgeGraphRootIds(normalized);
        setGraphNodes(normalized.nodes);
        setGraphEdges(normalized.edges);
        setGraphRootIds(rootIds);
      })
      .catch(() => {
        if (!mounted) return;
        setGraphNodes([]);
        setGraphEdges([]);
        setGraphRootIds([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    let mounted = true;

    courseService
      .getTeacherCourseHome(courseId)
      .then((data) => {
        if (mounted) setTeacherHome(data);
      })
      .catch(() => {
        if (mounted) setTeacherHome(EMPTY_TEACHER_HOME);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    let mounted = true;

    courseService
      .getTeacherCourseMaterials(courseId)
      .then((data) => {
        if (mounted) setCourseFiles(data.files);
      })
      .catch(() => {
        if (mounted) setCourseFiles([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    let mounted = true;

    Promise.all([
      courseService.getTeacherCourseTasks(courseId),
      courseService.getTeacherCourseQuestions(courseId),
      courseService.getTeacherCourseStudents(courseId),
      courseService.getCourseDiscussions('teacher', courseId),
    ])
      .then(([tasksData, questionsData, studentsData, discussionsData]) => {
        if (!mounted) return;
        setPublishedTasks(tasksData.tasks);
        setQuestions(questionsData.questions);
        setStudents(studentsData.students);
        setDiscussions(discussionsData.discussions);
      })
      .catch(() => {
        if (!mounted) return;
        setPublishedTasks([]);
        setQuestions([]);
        setStudents([]);
        setDiscussions([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  const indexedFileCount = courseFiles.filter((file) => isIndexedMaterialStatus(file.status)).length;
  const knowledgeHealth = courseFiles.length === 0 ? 0 : Math.round((indexedFileCount / courseFiles.length) * 100);

  // 新增：处理附件上传
  const handleAttachmentUpload = (e: React.ChangeEvent<HTMLInputElement>, formType: 'notice' | 'homework' | 'exam') => {
    const files = e.target.files;
    if (!files) return;
    
    const newFiles = Array.from(files);
    
    if (formType === 'notice') {
      setNoticeForm({ ...noticeForm, attachments: [...noticeForm.attachments, ...newFiles] });
    } else if (formType === 'homework') {
      setHomeworkForm({ ...homeworkForm, attachments: [...homeworkForm.attachments, ...newFiles] });
    } else if (formType === 'exam') {
      setExamForm({ ...examForm, attachments: [...examForm.attachments, ...newFiles] });
    }
  };

  // 新增：删除附件
  const removeAttachment = (index: number, formType: 'notice' | 'homework' | 'exam') => {
    if (formType === 'notice') {
      setNoticeForm({
        ...noticeForm,
        attachments: noticeForm.attachments.filter((_, i) => i !== index)
      });
    } else if (formType === 'homework') {
      setHomeworkForm({
        ...homeworkForm,
        attachments: homeworkForm.attachments.filter((_, i) => i !== index)
      });
    } else if (formType === 'exam') {
      setExamForm({
        ...examForm,
        attachments: examForm.attachments.filter((_, i) => i !== index)
      });
    }
  };

  // 新增：发布通知
  const handlePublishNotice = async () => {
    if (!noticeForm.title || !noticeForm.content) {
      alert('请填写完整的通知信息');
      return;
    }

    await courseService.publishNotice(courseId, {
      title: noticeForm.title,
      content: noticeForm.content,
      importance: noticeForm.importance,
      scope: noticeForm.scope,
      attachments: noticeForm.attachments.map(f => f.name),
    });
    
    // 模拟发布通知
    const newTask = {
      id: Date.now(),
      type: 'notice',
      title: noticeForm.title,
      deadline: '-',
      submitted: 68,
      total: 68,
      status: '已发布',
      publishDate: new Date().toISOString().split('T')[0],
      attachments: noticeForm.attachments.map(f => f.name)
    };
    
    setPublishedTasks([newTask, ...publishedTasks]);
    
    alert('通知发布成功！');
    setShowNoticeModal(false);
    setNoticeForm(createEmptyNoticeForm());
  };

  // 新增：创建作业
  const handleCreateHomework = async () => {
    if (!homeworkForm.title || !homeworkForm.deadline) {
      alert('请填写作业标题和截止时间');
      return;
    }
    if (homeworkForm.questions.some(q => !q.description)) {
      alert('请完善所有题目描述');
      return;
    }

    await courseService.createHomework(courseId, {
      title: homeworkForm.title,
      deadline: homeworkForm.deadline,
      allowLate: homeworkForm.allowLate,
      questions: homeworkForm.questions,
      attachments: homeworkForm.attachments.map(f => f.name),
    });
    
    // 模拟创建作业
    const newTask = {
      id: Date.now(),
      type: 'homework',
      title: homeworkForm.title,
      deadline: homeworkForm.deadline,
      submitted: 0,
      total: 68,
      status: '进行中',
      publishDate: new Date().toISOString().split('T')[0],
      attachments: homeworkForm.attachments.map(f => f.name)
    };
    
    setPublishedTasks([newTask, ...publishedTasks]);
    
    alert('作业创建成功！');
    setShowHomeworkModal(false);
    setHomeworkForm(createEmptyHomeworkForm());
  };

  // 新增：添加作业题目
  const addHomeworkQuestion = () => {
    setHomeworkForm({
      ...homeworkForm,
      questions: [...homeworkForm.questions, createEmptyHomeworkQuestion()]
    });
  };

  // 新增：删除作业题目
  const removeHomeworkQuestion = (index: number) => {
    setHomeworkForm({
      ...homeworkForm,
      questions: homeworkForm.questions.filter((_, i) => i !== index)
    });
  };

  // 新增：AI智能组卷
  const handleGenerateQuestions = async () => {
    setIsGeneratingQuestions(true);
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const questionTypes = ['单选题', '多选题', '判断题', '填空题', '简答题'];
    const generated = Array.from({ length: examForm.questionCount }, (_, i) => ({
      type: questionTypes[Math.floor(Math.random() * questionTypes.length)],
      content: `第${i + 1}题：这是一道关于计算机网络的${questionTypes[Math.floor(Math.random() * questionTypes.length)]}`,
      score: Math.floor(examForm.totalScore / examForm.questionCount)
    }));
    
    setExamForm({ ...examForm, generatedQuestions: generated });
    setIsGeneratingQuestions(false);
  };

  // 新增：创建考试
  const handleCreateExam = async () => {
    if (!examForm.name || !examForm.startTime || !examForm.endTime) {
      alert('请填写完整的考试信息');
      return;
    }
    if (examForm.generatedQuestions.length === 0) {
      alert('请先生成试卷题目');
      return;
    }

    await courseService.createExam(courseId, {
      name: examForm.name,
      startTime: examForm.startTime,
      endTime: examForm.endTime,
      duration: examForm.duration,
      totalScore: examForm.totalScore,
      questions: examForm.generatedQuestions,
      attachments: examForm.attachments.map(f => f.name),
    });
    
    // 模拟创建考试
    const newTask = {
      id: Date.now(),
      type: 'exam',
      title: examForm.name,
      startTime: examForm.startTime,
      deadline: examForm.endTime,
      duration: examForm.duration,
      submitted: 0,
      total: 68,
      status: '未开始',
      publishDate: new Date().toISOString().split('T')[0],
      attachments: examForm.attachments.map(f => f.name)
    };
    
    setPublishedTasks([newTask, ...publishedTasks]);
    
    alert('考试创建成功！');
    setShowExamModal(false);
    setExamForm(createEmptyExamForm());
  };

  // 新增：获取过滤后的任务列表
  const getFilteredTasks = () => {
    if (taskFilter === 'all') return publishedTasks;
    return publishedTasks.filter(task => task.type === taskFilter);
  };

  // 新增：查看任务详情
  const viewTaskDetail = async (task: TeacherCourseTask) => {
    setCurrentTask(buildTaskDetailFallback(task));
    setTaskDetailError('');
    setIsTaskDetailLoading(true);
    setShowTaskDetailModal(true);

    try {
      const detail = await courseService.getTeacherCourseTaskDetail(courseId, task.id);
      setCurrentTask(detail);
    } catch {
      setTaskDetailError('任务详情加载失败，当前先展示列表中的基础信息。');
    } finally {
      setIsTaskDetailLoading(false);
    }
  };

  // 新增：更新任务状态
  const updateTaskStatus = async (taskId: number, newStatus: string) => {
    await courseService.updateTeacherCourseTaskStatus(courseId, taskId, {
      status: newStatus,
    });

    setPublishedTasks(prev => prev.map(task => 
      task.id === taskId ? { ...task, status: newStatus } : task
    ));

    setCurrentTask(prev => prev ? { ...prev, status: newStatus } : prev);
    
    alert(`任务状态已更新为：${newStatus}`);
  };

  // 新增：切换问题展开/收起
  const toggleQuestion = (questionId: number) => {
    setExpandedQuestions(prev => 
      prev.includes(questionId) 
        ? prev.filter(id => id !== questionId)
        : [...prev, questionId]
    );
  };

  // 新增：开始回复
  const startReply = (questionId: number) => {
    setReplyingTo(questionId);
    setReplyContent('');
  };

  // 新增：取消回复
  const cancelReply = () => {
    setReplyingTo(null);
    setReplyContent('');
  };

  // 新增：提交回复
  const submitReply = async (questionId: number) => {
    if (!replyContent.trim()) return;

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    await courseService.replyTeacherQuestion(courseId, questionId, {
      content: replyContent,
      author: '王教授',
    });

    setQuestions(prev => prev.map(q => {
      if (q.id === questionId) {
        return {
          ...q,
          status: 'answered',
          replies: [...q.replies, {
            author: '王教授',
            content: replyContent,
            time: timeStr
          }]
        };
      }
      return q;
    }));

    setReplyingTo(null);
    setReplyContent('');
  };

  // 新增：查看AI回答
  const viewAIAnswer = async (question: TeacherCourseQuestion) => {
    setCurrentAIAnswer(buildAiAnswerFallback(question));
    setAiAnswerError('');
    setIsAIAnswerLoading(true);
    setShowAIAnswerModal(true);

    try {
      const aiAnswerDetail = await aiService.getTeacherAiQuestionDetail(question.id);
      setCurrentAIAnswer(aiAnswerDetail);
    } catch {
      setAiAnswerError('AI 回答加载失败，当前先展示基础占位数据。');
    } finally {
      setIsAIAnswerLoading(false);
    }
  };

  // 新增：采纳AI回答
  const adoptAIAnswer = async () => {
    if (!currentAIAnswer) return;

    await aiService.adoptAiAnswer(currentAIAnswer.id);

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    const questionToUpdate = questions.find(q => q.id === currentAIAnswer.id);
    if (questionToUpdate) {
      setQuestions(prev => prev.map(q => {
        if (q.id === currentAIAnswer.id) {
          return {
            ...q,
            status: 'answered',
            replies: [...q.replies, {
              author: 'AI助教',
              content: currentAIAnswer.aiAnswer,
              time: timeStr
            }]
          };
        }
        return q;
      }));
    }

    setShowAIAnswerModal(false);
    setCurrentAIAnswer(null);
  };

  // 新增：自行回复（关闭AI回答弹窗并打开回复区）
  const replyManually = () => {
    const questionToReply = questions.find(q => q.id === currentAIAnswer?.id);
    if (questionToReply) {
      setReplyingTo(questionToReply.id);
      setExpandedQuestions(prev => prev.includes(questionToReply.id) ? prev : [...prev, questionToReply.id]);
    }
    setShowAIAnswerModal(false);
    setCurrentAIAnswer(null);
  };

  // 新增：学生管理相关函数
  const getFilteredStudents = () => {
    let filtered = students;
    
    // 按分组过滤
    if (studentGroupTab === 'warning') {
      filtered = filtered.filter(s => s.status === 'warning');
    } else if (studentGroupTab !== 'all') {
      const groupNum = parseInt(studentGroupTab.replace('group', ''));
      filtered = filtered.filter(s => s.group === groupNum);
    }
    
    // 按搜索关键词过滤
    if (studentSearchQuery.trim()) {
      const query = studentSearchQuery.toLowerCase();
      filtered = filtered.filter(s => 
        s.name.toLowerCase().includes(query) || 
        s.studentId.toLowerCase().includes(query)
      );
    }
    
    return filtered;
  };

  const handleSendWarningReminder = async (studentId: number) => {
    const student = students.find(s => s.id === studentId);
    if (student) {
      await courseService.sendWarningReminder(courseId, studentId);
      alert(`已向 ${student.name}（${student.studentId}）发送学习提醒`);
    }
  };

  const handleMoveStudentsToGroup = async () => {
    if (selectedStudents.length === 0) {
      alert('请先选择要移动的学生');
      return;
    }

    await courseService.moveStudentsToGroup(courseId, {
      studentIds: selectedStudents,
      targetGroup,
    });
    
    setStudents(prev => prev.map(s => 
      selectedStudents.includes(s.id) ? { ...s, group: targetGroup } : s
    ));
    
    setSelectedStudents([]);
    alert(`已将 ${selectedStudents.length} 名学生移动到第${targetGroup}组`);
  };

  const handleExport = async () => {
    const selectedFields = Object.entries(exportForm.fields)
      .filter(([_, checked]) => checked)
      .map(([field]) => field);
    
    if (selectedFields.length === 0) {
      alert('请至少选择一个导出字段');
      return;
    }
    
    const studentsToExport = exportForm.scope === 'current' ? getFilteredStudents() : students;
    await courseService.exportStudents(courseId, {
      fields: selectedFields,
      scope: exportForm.scope,
      format: exportForm.format,
      studentIds: studentsToExport.map((student) => student.id),
    });
    
    alert(`导出成功！已导出 ${studentsToExport.length} 名学生的数据（${exportForm.format.toUpperCase()}格式）`);
    setShowExportModal(false);
  };

  // 新增：切换文件展开状态
  const toggleFileExpand = (fileId: CourseFileId) => {
    setExpandedFiles(prev => 
      prev.includes(fileId) 
        ? prev.filter(id => id !== fileId)
        : [...prev, fileId]
    );
  };

  // 新增：打开文件菜单
  const openFileMenu = (e: React.MouseEvent, fileId: CourseFileId) => {
    e.stopPropagation();
    setShowFileMenu(showFileMenu === fileId ? null : fileId);
  };

  // 新增：预览文件
  const handlePreviewFile = async (file: TeacherCourseFile) => {
    setCurrentFile(file);
    setCurrentFilePreview(buildMaterialPreviewFallback(file));
    setFilePreviewError('');
    setIsFilePreviewLoading(true);
    setShowPreviewModal(true);
    setShowFileMenu(null);

    try {
      const preview = await courseService.getTeacherCourseMaterialPreview(courseId, file.id);
      setCurrentFilePreview(preview);
    } catch {
      setFilePreviewError('文件预览加载失败，当前先展示基础占位信息。');
    } finally {
      setIsFilePreviewLoading(false);
    }
  };

  // 新增：下载文件
  const handleDownloadFile = async (file: TeacherCourseFile) => {
    setDownloadingFileId(file.id);

    try {
      const download = await courseService.downloadTeacherCourseFile(courseId, file.id);
      const link = document.createElement('a');
      link.href = download.downloadUrl;
      link.download = download.fileName;
      link.rel = 'noopener';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setCourseFiles(prev => prev.map((item) => (
        item.id === file.id ? { ...item, downloads: item.downloads + 1 } : item
      )));
      setCurrentFile(prev => (
        prev && prev.id === file.id ? { ...prev, downloads: prev.downloads + 1 } : prev
      ));
    } catch {
      alert(`下载 ${file.name} 失败，请稍后重试`);
    } finally {
      setDownloadingFileId(null);
    }

    setShowFileMenu(null);
  };

  // 新增：AI解析文件
  const handleAIAnalysis = async (file: TeacherCourseFile) => {
    setCurrentFile(file);
    setCurrentFileAnalysis(buildMaterialAnalysisFallback(file));
    setFileAnalysisError('');
    setIsFileAnalysisLoading(true);
    setShowAIAnalysisModal(true);
    setShowFileMenu(null);

    try {
      const analysis = await courseService.getTeacherCourseMaterialAnalysis(courseId, file.id);
      setCurrentFileAnalysis(analysis);
    } catch {
      setFileAnalysisError('AI 解析结果加载失败，当前先展示基础占位数据。');
    } finally {
      setIsFileAnalysisLoading(false);
    }
  };

  // 新增：删除文件
  const handleDeleteFile = async (fileId: CourseFileId) => {
    if (confirm('确定要删除这个文件吗？')) {
      await courseService.deleteTeacherCourseFile(courseId, fileId);
      setCourseFiles(prev => prev.filter(f => f.id !== fileId));
      alert('文件已删除');
    }
    setShowFileMenu(null);
  };

  // 新增：重命名文件
  const handleRenameFile = (file: TeacherCourseFile) => {
    setCurrentFile(file);
    setRenameValue(file.name);
    setShowRenameModal(true);
    setShowFileMenu(null);
  };

  // 新增：确认重命名
  const confirmRename = async () => {
    if (!renameValue.trim()) {
      alert('文件名不能为空');
      return;
    }
    if (!currentFile) return;
    await courseService.renameTeacherCourseFile(courseId, currentFile.id, renameValue);
    setCourseFiles(prev => prev.map(f => 
      f.id === currentFile.id ? { ...f, name: renameValue } : f
    ));
    setShowRenameModal(false);
    setRenameValue('');
    alert('重命名成功');
  };

  // 新增：分享文件
  const handleShareFile = (file: TeacherCourseFile) => {
    setCurrentFile(file);
    setShowShareModal(true);
    setShowFileMenu(null);
  };

  // 新增：获取过滤和排序后的文件列表
  const getFilteredAndSortedFiles = () => {
    let filtered = courseFiles;
    
    // 按类型过滤
    if (fileFilter !== 'all') {
      filtered = filtered.filter(f => f.category === fileFilter);
    }
    
    // 排序
    const sorted = [...filtered].sort((a, b) => {
      if (fileSortBy === 'date') {
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      } else if (fileSortBy === 'name') {
        return a.name.localeCompare(b.name);
      } else if (fileSortBy === 'downloads') {
        return b.downloads - a.downloads;
      } else if (fileSortBy === 'size') {
        const sizeA = parseFloat(a.size);
        const sizeB = parseFloat(b.size);
        return sizeB - sizeA;
      }
      return 0;
    });
    
    return sorted;
  };

  // 新增：切换讨论展开状态
  const toggleDiscussion = (discussionId: number) => {
    setExpandedDiscussions(prev => 
      prev.includes(discussionId) 
        ? prev.filter(id => id !== discussionId)
        : [...prev, discussionId]
    );
  };

  // 新增：开始回复讨论
  const startReplyDiscussion = (discussionId: number) => {
    setReplyingToDiscussion(discussionId);
    setDiscussionReplyContent('');
  };

  // 新增：取消回复讨论
  const cancelReplyDiscussion = () => {
    setReplyingToDiscussion(null);
    setDiscussionReplyContent('');
  };

  // 新增：提交讨论回复
  const submitDiscussionReply = async (discussionId: number) => {
    if (!discussionReplyContent.trim()) return;

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    await courseService.replyDiscussion('teacher', courseId, discussionId, {
      content: discussionReplyContent,
      author: '王教授',
    });

    setDiscussions(prev => prev.map(d => {
      if (d.id === discussionId) {
        return {
          ...d,
          replies: [...d.replies, {
            author: '王教授',
            content: discussionReplyContent,
            time: timeStr,
            isTeacher: true
          }]
        };
      }
      return d;
    }));

    setReplyingToDiscussion(null);
    setDiscussionReplyContent('');
  };

  // 新增：点赞讨论
  const toggleLikeDiscussion = async (discussionId: number) => {
    await courseService.toggleDiscussionLike('teacher', courseId, discussionId);
    setDiscussions(prev => prev.map(d => {
      if (d.id === discussionId) {
        return {
          ...d,
          liked: !d.liked,
          likes: d.liked ? d.likes - 1 : d.likes + 1
        };
      }
      return d;
    }));
  };

  // 新增：置顶讨论
  const togglePinDiscussion = async (discussionId: number) => {
    await courseService.togglePinDiscussion(courseId, discussionId);
    setDiscussions(prev => prev.map(d => {
      if (d.id === discussionId) {
        return { ...d, pinned: !d.pinned };
      }
      return d;
    }));
  };

  // 新增：发布新讨论
  const handlePublishDiscussion = async () => {
    if (!newDiscussionForm.title.trim() || !newDiscussionForm.content.trim()) {
      alert('请填写完整的讨论标题和内容');
      return;
    }

    await courseService.createDiscussion('teacher', courseId, {
      title: newDiscussionForm.title,
      content: newDiscussionForm.content,
      pinned: newDiscussionForm.pinned,
    });

    const newDiscussion = {
      id: Date.now(),
      student: '王教授',
      title: newDiscussionForm.title,
      content: newDiscussionForm.content,
      replies: [],
      likes: 0,
      time: '刚刚',
      pinned: newDiscussionForm.pinned,
      liked: false
    };

    setDiscussions([newDiscussion, ...discussions]);

    alert('讨论发布成功！');
    setShowNewDiscussionModal(false);
    setNewDiscussionForm(createEmptyDiscussionForm());
  };

  // 新增：获取排序后的讨论列表（置顶在前）
  const getSortedDiscussions = () => {
    return [...discussions].sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });
  };

  const averageStudentProgress =
    students.length > 0
      ? Math.round(students.reduce((sum, s) => sum + s.progress, 0) / students.length)
      : 0;
  const averageStudentAttendance =
    students.length > 0
      ? Math.round(students.reduce((sum, s) => sum + s.attendance, 0) / students.length)
      : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部主导航栏 */}
      <nav className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link to="/teacher-dashboard" className="flex items-center gap-2">
                <img src="https://public.readdy.ai/ai/img_res/2625f127-2f4f-41ee-82d8-6c2fa4dee4ac.png" alt="珞樱学堂" className="h-9 w-9" />
                <span className="text-lg font-semibold text-gray-900">珞樱学堂</span>
              </Link>
              <div className="h-6 w-px bg-gray-300"></div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
                  <i className="ri-book-open-line text-white text-base"></i>
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-900">{course.name}</div>
                  <div className="text-xs text-gray-500">
                    {course.code} · {course.teacher}
                    {bootstrap && ` · ${bootstrap.studentCount}名学生 · ${bootstrap.materialCount}份资料`}
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">王</div>
            </div>
          </div>
        </div>
      </nav>

      <div className="flex pt-16">
        {/* 左侧二级导航栏 */}
        <aside className="fixed left-0 top-16 bottom-0 w-56 bg-white border-r border-gray-200 overflow-y-auto">
          <div className="p-3">
            {[
              { key: 'home', icon: 'ri-home-4-line', label: '班级首页' },
              { key: 'knowledge', icon: 'ri-book-2-line', label: '课程知识' },
              { key: 'tasks', icon: 'ri-task-line', label: '任务发布' },
              { key: 'interaction', icon: 'ri-chat-3-line', label: '互动空间' },
              { key: 'students', icon: 'ri-group-line', label: '学生管理' },
              { key: 'ai', icon: 'ri-robot-line', label: 'AI助教' },
            ].map(item => (
              <button
                key={item.key}
                onClick={() => setActiveSection(item.key)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
                  activeSection === item.key ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <i className={`${item.icon} text-base`}></i>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* 右侧内容区 */}
        <main className="ml-56 flex-1 p-6">
          {courseError && (
            <div className="mx-auto mb-4 max-w-6xl rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-700">
              {courseError}
            </div>
          )}
          {activeSection === 'home' && (
            <div className="max-w-6xl mx-auto space-y-5">
              {/* Page title + invite code row */}
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">班级首页</h1>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg">
                    <span className="text-xs text-gray-500">邀请码</span>
                    <span className="text-base font-bold text-gray-900 tracking-widest">{bootstrap?.inviteCode || teacherHome.inviteCode}</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(bootstrap?.inviteCode || teacherHome.inviteCode)}
                      className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-teal-600 cursor-pointer transition-colors"
                    >
                      <i className="ri-file-copy-line text-sm"></i>
                    </button>
                  </div>
                  <button
                    onClick={() => setShowNoticeModal(true)}
                    className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-add-line"></i>发布通知
                  </button>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-5 gap-4">
                {teacherHome.stats.map((stat, i) => (
                  <div key={i} className="bg-white rounded-xl p-4 border border-gray-200">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs text-gray-500">{stat.label}</span>
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${stat.iconBg}`}>
                        <i className={`${stat.icon} ${stat.iconColor} text-base`}></i>
                      </div>
                    </div>
                    <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
                    <div className={`text-xs mt-1 flex items-center gap-1 ${stat.trend === 'up' ? 'text-green-600' : stat.trend === 'warn' ? 'text-red-500' : 'text-gray-500'}`}>
                      {stat.trend === 'up' && <i className="ri-arrow-up-line text-xs"></i>}
                      {stat.trend === 'warn' && <i className="ri-error-warning-line text-xs"></i>}
                      {stat.sub}
                    </div>
                  </div>
                ))}
              </div>

              {/* Middle row: recent tasks full-width */}
              <div className="bg-white rounded-xl p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-gray-900">近期任务</h2>
                  <div className="flex items-center gap-3">
                    <button onClick={() => { setShowNoticeModal(true); }} className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap transition-colors">
                      <i className="ri-notification-line text-sm"></i>发通知
                    </button>
                    <button onClick={() => { setShowHomeworkModal(true); }} className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap transition-colors">
                      <i className="ri-file-text-line text-sm"></i>布作业
                    </button>
                    <button onClick={() => { setShowExamModal(true); }} className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap transition-colors">
                      <i className="ri-file-list-line text-sm"></i>创考试
                    </button>
                    <div className="w-px h-4 bg-gray-200"></div>
                    <button onClick={() => setActiveSection('tasks')} className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看全部</button>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-3">
                  {teacherHome.recentTasks.map((task, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-gray-200 hover:bg-gray-50/50 cursor-pointer transition-colors">
                      <div className={`w-9 h-9 flex items-center justify-center rounded-lg flex-shrink-0 ${task.type === 'homework' ? 'bg-green-50' : task.type === 'exam' ? 'bg-amber-50' : 'bg-teal-50'}`}>
                        <i className={`text-base ${task.type === 'homework' ? 'ri-file-text-line text-green-600' : task.type === 'exam' ? 'ri-file-list-line text-amber-600' : 'ri-notification-line text-teal-600'}`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-gray-900 truncate">{task.title}</div>
                        <div className="text-xs text-gray-400 mt-0.5">{task.deadline !== '-' ? `截止 ${task.deadline}` : '已发布'} · {task.submitted}/{task.total}</div>
                      </div>
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${task.statusColor}`}>{task.status}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom row: warning students + activity feed + weekly stats */}
              <div className="grid grid-cols-3 gap-5">
                {/* Warning students */}
                <div className="bg-white rounded-xl p-5 border border-orange-100">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <i className="ri-alert-line text-orange-500"></i>
                      <h2 className="text-sm font-semibold text-gray-900">预警学生</h2>
                      <span className="flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-orange-500 rounded-full">
                        {teacherHome.warningStudents.length}
                      </span>
                    </div>
                    <button onClick={() => setActiveSection('students')} className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">管理</button>
                  </div>
                  <div className="space-y-3">
                    {teacherHome.warningStudents.map((student, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-orange-50/50 rounded-xl border border-orange-100">
                        <div className="w-8 h-8 rounded-full bg-orange-400 flex items-center justify-center text-white text-xs font-medium flex-shrink-0">{student.avatar}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-gray-900">{student.name}</span>
                            <span className="text-xs text-gray-400">{student.id}</span>
                          </div>
                          <div className="text-xs text-orange-600 mb-1.5">{student.reason}</div>
                          <div className="flex items-center gap-3">
                            <div className="flex items-center gap-1">
                              <span className="text-xs text-gray-500">进度</span>
                              <div className="w-14 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div className="h-full bg-red-400 rounded-full" style={{ width: `${student.progress}%` }}></div>
                              </div>
                              <span className="text-xs text-red-500 font-medium">{student.progress}%</span>
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => {}}
                          className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-100 text-orange-600 hover:bg-orange-200 cursor-pointer flex-shrink-0 transition-colors"
                          title="发送提醒"
                        >
                          <i className="ri-mail-send-line text-sm"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Activity feed */}
                <div className="bg-white rounded-xl p-5 border border-gray-200">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-gray-900">班级动态</h2>
                    <span className="text-xs text-gray-400">实时更新</span>
                  </div>
                  <div className="space-y-0">
                    {teacherHome.activities.map((item, i) => (
                      <div
                        key={i}
                        className={`flex items-start gap-3 py-2.5 ${i < teacherHome.activities.length - 1 ? 'border-b border-gray-50' : ''}`}
                      >
                        <div className={`w-7 h-7 rounded-full ${item.color} flex items-center justify-center text-white text-xs font-medium flex-shrink-0`}>{item.avatar}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-gray-800 leading-snug">
                            <span className="font-medium">{item.name}</span>
                            <span className="text-gray-500"> {item.action}</span>
                          </div>
                          <div className="text-xs text-gray-400 truncate mt-0.5">{item.detail}</div>
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0 whitespace-nowrap">{item.time}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Weekly stats + quick info */}
                <div className="flex flex-col gap-4">
                  {/* Weekly overview */}
                  <div className="bg-white rounded-xl p-5 border border-gray-200 flex-1">
                    <h2 className="text-sm font-semibold text-gray-900 mb-4">本周概况</h2>
                    <div className="grid grid-cols-2 gap-3">
                      {teacherHome.weeklyStats.map((s, i) => (
                        <div key={i} className={`flex items-center gap-2.5 p-3 rounded-xl ${s.bg}`}>
                          <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                            <i className={`${s.icon} ${s.color} text-lg`}></i>
                          </div>
                          <div>
                            <div className="text-sm font-bold text-gray-900">{s.value}<span className="text-xs font-normal text-gray-500 ml-0.5">{s.unit}</span></div>
                            <div className="text-xs text-gray-500">{s.label}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Group overview */}
                  <div className="bg-white rounded-xl p-5 border border-gray-200">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-sm font-semibold text-gray-900">小组表现</h2>
                    </div>
                    <div className="space-y-2.5">
                      {teacherHome.groupPerformance.map((g, i) => (
                        <div key={i} className="flex items-center gap-3">
                          <div className={`w-2 h-8 rounded-full flex-shrink-0 ${g.color}`}></div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-medium text-gray-800">{g.name}</span>
                              <span className="text-xs font-semibold text-gray-700">{g.avg}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${g.color}`} style={{ width: `${g.avg}%` }}></div>
                            </div>
                          </div>
                          <span className="text-xs text-gray-400 flex-shrink-0">{g.members}人</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'knowledge' && (
            <div className="max-w-6xl mx-auto">
              <div className="flex items-center justify-between mb-6">
                <h1 className="text-xl font-bold text-gray-900">课程知识</h1>
                <button 
                  onClick={() => setShowUploadModal(true)}
                  className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  <i className="ri-upload-line mr-1"></i>上传资料
                </button>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">资料总数</span>
                    <i className="ri-file-line text-blue-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{courseFiles.length}</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">知识图谱节点</span>
                    <i className="ri-node-tree text-green-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{graphNodes.length}</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">知识库健康度</span>
                    <i className="ri-heart-pulse-line text-teal-600 text-lg"></i>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div className="h-full bg-teal-500 rounded-full" style={{ width: `${knowledgeHealth}%` }}></div>
                    </div>
                    <span className="text-sm font-semibold text-gray-900">{knowledgeHealth}%</span>
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 mb-5">
                <div className="px-5 py-4 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-gray-900">课程资料</h2>
                    <div className="flex items-center gap-3">
                      <select
                        value={fileFilter}
                        onChange={(e) => setFileFilter(e.target.value)}
                        className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-white cursor-pointer"
                      >
                        <option value="all">全部类型</option>
                        <option value="lecture">课件</option>
                        <option value="video">视频</option>
                        <option value="lab">实验</option>
                        <option value="exercise">习题</option>
                      </select>
                      <select
                        value={fileSortBy}
                        onChange={(e) => setFileSortBy(e.target.value)}
                        className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-white cursor-pointer"
                      >
                        <option value="date">按日期排序</option>
                        <option value="name">按名称排序</option>
                        <option value="downloads">按下载量排序</option>
                        <option value="size">按大小排序</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div className="divide-y divide-gray-100">
                  {getFilteredAndSortedFiles().length === 0 && (
                    <TeacherCourseEmptyState
                      icon="ri-folder-open-line"
                      title="暂无课程资料"
                      description="教师尚未上传资料或当前筛选无结果时会显示这里。"
                    />
                  )}
                  {getFilteredAndSortedFiles().map((file) => (
                    <div key={file.id}>
                      <div 
                        className="px-5 py-4 hover:bg-gray-50 cursor-pointer"
                        onClick={() => toggleFileExpand(file.id)}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 flex items-center justify-center rounded-lg ${file.type === 'PDF' ? 'bg-red-50' : file.type === 'PPT' ? 'bg-orange-50' : 'bg-purple-50'}`}>
                            <i className={`text-lg ${file.type === 'PDF' ? 'ri-file-pdf-line text-red-600' : file.type === 'PPT' ? 'ri-file-ppt-line text-orange-600' : 'ri-video-line text-purple-600'}`}></i>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-900">{file.name}</div>
                            <div className="text-xs text-gray-500 mt-1">{file.size} · {file.date} · {file.downloads}次下载</div>
                          </div>
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getMaterialStatusMeta(file.status).className}`}>{getMaterialStatusMeta(file.status).label}</span>
                          <button 
                            onClick={(e) => openFileMenu(e, file.id)}
                            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer relative"
                          >
                            <i className="ri-more-2-fill text-lg"></i>
                            {showFileMenu === file.id && (
                              <div className="absolute right-0 top-full mt-1 w-40 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handlePreviewFile(file);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                                >
                                  <i className="ri-eye-line"></i>预览
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handleDownloadFile(file);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                                >
                                  <i className="ri-download-line"></i>下载
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handleAIAnalysis(file);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                                >
                                  <i className="ri-robot-line"></i>AI解析
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRenameFile(file);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                                >
                                  <i className="ri-edit-line"></i>重命名
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleShareFile(file);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                                >
                                  <i className="ri-share-line"></i>分享
                                </button>
                                <div className="border-t border-gray-100 my-1"></div>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteFile(file.id);
                                  }}
                                  className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                                >
                                  <i className="ri-delete-bin-line"></i>删除
                                </button>
                              </div>
                            )}
                          </button>
                          <i className={expandedFiles.includes(file.id) ? 'ri-arrow-up-s-line text-gray-400' : 'ri-arrow-down-s-line text-gray-400'}></i>
                        </div>
                      </div>
                      
                      {/* 展开的详细信息 */}
                      {expandedFiles.includes(file.id) && (
                        <div className="px-5 py-4 bg-gray-50 border-t border-gray-100">
                          <div className="grid grid-cols-2 gap-4 mb-4">
                            <div>
                              <div className="text-xs text-gray-500 mb-1">文件类型</div>
                              <div className="text-sm text-gray-900">{file.type}</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">文件大小</div>
                              <div className="text-sm text-gray-900">{file.size}</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">上传日期</div>
                              <div className="text-sm text-gray-900">{file.date}</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">下载次数</div>
                              <div className="text-sm text-gray-900">{file.downloads}次</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">解析状态</div>
                              <div className="text-sm text-gray-900">{getMaterialStatusMeta(file.status).label}</div>
                            </div>
                            <div>
                              <div className="text-xs text-gray-500 mb-1">知识点数量</div>
                              <div className="text-sm text-gray-900">{Math.floor(Math.random() * 50) + 20}个</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => { void handlePreviewFile(file); }}
                              className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                            >
                              <i className="ri-eye-line mr-1"></i>预览
                            </button>
                            <button
                              onClick={() => { void handleDownloadFile(file); }}
                              className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 cursor-pointer whitespace-nowrap"
                            >
                              <i className="ri-download-line mr-1"></i>下载
                            </button>
                            <button
                              onClick={() => { void handleAIAnalysis(file); }}
                              className="px-3 py-1.5 text-xs font-medium text-purple-600 bg-purple-50 rounded-md hover:bg-purple-100 cursor-pointer whitespace-nowrap"
                            >
                              <i className="ri-robot-line mr-1"></i>AI解析
                            </button>
                            <button
                              onClick={() => handleShareFile(file)}
                              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                            >
                              <i className="ri-share-line mr-1"></i>分享
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <KnowledgeGraphViewer
                nodes={graphNodes}
                edges={graphEdges}
                rootIds={graphRootIds}
                heightClassName="h-[520px]"
              />
            </div>
          )}

          {activeSection === 'tasks' && (
            <div className="max-w-6xl mx-auto">
              <h1 className="text-xl font-bold text-gray-900 mb-6">任务发布</h1>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <button 
                  onClick={() => setShowNoticeModal(true)}
                  className="bg-white rounded-lg p-5 border border-gray-200 hover:border-teal-500 hover:shadow-md transition-all cursor-pointer"
                >
                  <div className="w-12 h-12 flex items-center justify-center rounded-lg bg-blue-50 mb-3">
                    <i className="ri-notification-line text-blue-600 text-2xl"></i>
                  </div>
                  <div className="text-base font-semibold text-gray-900 mb-1">发布通知</div>
                  <div className="text-xs text-gray-500">向学生推送课程通知</div>
                </button>
                <button 
                  onClick={() => setShowHomeworkModal(true)}
                  className="bg-white rounded-lg p-5 border border-gray-200 hover:border-teal-500 hover:shadow-md transition-all cursor-pointer"
                >
                  <div className="w-12 h-12 flex items-center justify-center rounded-lg bg-green-50 mb-3">
                    <i className="ri-file-text-line text-green-600 text-2xl"></i>
                  </div>
                  <div className="text-base font-semibold text-gray-900 mb-1">创建作业</div>
                  <div className="text-xs text-gray-500">多题型作业创建</div>
                </button>
                <button 
                  onClick={() => setShowExamModal(true)}
                  className="bg-white rounded-lg p-5 border border-gray-200 hover:border-teal-500 hover:shadow-md transition-all cursor-pointer"
                >
                  <div className="w-12 h-12 flex items-center justify-center rounded-lg bg-purple-50 mb-3">
                    <i className="ri-file-list-line text-purple-600 text-2xl"></i>
                  </div>
                  <div className="text-base font-semibold text-gray-900 mb-1">创建考试</div>
                  <div className="text-xs text-gray-500">智能组卷与考试管理</div>
                </button>
              </div>
              <div className="bg-white rounded-lg border border-gray-200">
                <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900">已发布任务</h2>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => setTaskFilter('all')}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${taskFilter === 'all' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      全部
                    </button>
                    <button 
                      onClick={() => setTaskFilter('notice')}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${taskFilter === 'notice' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      通知
                    </button>
                    <button 
                      onClick={() => setTaskFilter('homework')}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${taskFilter === 'homework' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      作业
                    </button>
                    <button 
                      onClick={() => setTaskFilter('exam')}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${taskFilter === 'exam' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      考试
                    </button>
                  </div>
                </div>
                <div className="divide-y divide-gray-100">
                  {getFilteredTasks().length === 0 && (
                    <TeacherCourseEmptyState
                      icon="ri-task-line"
                      title="暂无任务"
                      description="当前筛选下没有通知、作业或考试，发布后会显示在这里。"
                    />
                  )}
                  {getFilteredTasks().map((task) => (
                    <div key={task.id} className="px-5 py-4 hover:bg-gray-50 cursor-pointer" onClick={() => { void viewTaskDetail(task); }}>
                      <div className="flex items-center gap-4">
                        <div className={`w-10 h-10 flex items-center justify-center rounded-lg ${task.type === 'homework' ? 'bg-green-50' : task.type === 'exam' ? 'bg-purple-50' : 'bg-blue-50'}`}>
                          <i className={`text-lg ${task.type === 'homework' ? 'ri-file-text-line text-green-600' : task.type === 'exam' ? 'ri-file-list-line text-purple-600' : 'ri-notification-line text-blue-600'}`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900">{task.title}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {task.type === 'exam' && (task as any).startTime && `开放: ${(task as any).startTime} ~ `}
                            {task.deadline !== '-' && (task.type === 'exam' ? task.deadline : `截止时间: ${task.deadline}`)}
                            {task.type === 'exam' && (task as any).duration && ` · 答题时长 ${(task as any).duration} 分钟`}
                            {task.type !== 'notice' && task.type !== 'exam' && ` · 已提交 ${task.submitted}/${task.total}`}
                            {task.type === 'exam' && ` · 已提交 ${task.submitted}/${task.total}`}
                            {task.attachments.length > 0 && ` · ${task.attachments.length}个附件`}
                          </div>
                        </div>
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${task.status === '进行中' ? 'bg-blue-50 text-blue-600' : task.status === '未开始' ? 'bg-gray-100 text-gray-600' : task.status === '已结束' ? 'bg-gray-100 text-gray-500' : 'bg-green-50 text-green-600'}`}>{task.status}</span>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            // 显示更多操作菜单
                          }}
                          className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                        >
                          <i className="ri-more-2-fill text-lg"></i>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'interaction' && (
            <div className="max-w-6xl mx-auto">
              <h1 className="text-xl font-bold text-gray-900 mb-6">互动空间</h1>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">待审核疑问</span>
                    <i className="ri-question-line text-orange-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{questions.filter(q => q.status === 'pending').length}</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">相似问题</span>
                    <i className="ri-file-copy-line text-blue-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">12</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">讨论帖</span>
                    <i className="ri-chat-3-line text-green-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">28</div>
                </div>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 mb-5">
                <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900">待审核疑问队列</h2>
                  <button className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap">集中答疑</button>
                </div>
                <div className="divide-y divide-gray-100">
                  {questions.length === 0 && (
                    <TeacherCourseEmptyState
                      icon="ri-question-answer-line"
                      title="暂无待审核疑问"
                      description="学生提问或 AI 低置信回答需要人工审核时，会显示在这里。"
                    />
                  )}
                  {questions.map((item) => (
                    <div key={item.id} className="px-5 py-4 hover:bg-gray-50">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-medium flex-shrink-0">{item.student[0]}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-gray-900">{item.student}</span>
                            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${item.confidence === 'low' ? 'bg-red-50 text-red-600' : 'bg-yellow-50 text-yellow-600'}`}>
                              AI置信度{item.confidence === 'low' ? '低' : '中'}
                            </span>
                            {item.status === 'answered' && (
                              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-50 text-green-600">已回复</span>
                            )}
                          </div>
                          <div className="text-sm text-gray-700 mb-2">{item.question}</div>
                          
                          {/* 回复列表 */}
                          {item.replies.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {item.replies.map((reply, idx) => (
                                <div key={idx} className="flex items-start gap-2 p-3 bg-teal-50 rounded-lg border border-teal-100">
                                  <div className="w-6 h-6 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                                    {reply.author === 'AI助教' ? <i className="ri-robot-line"></i> : reply.author[0]}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs font-medium text-gray-900">{reply.author}</span>
                                      <span className="text-xs text-gray-400">{reply.time}</span>
                                    </div>
                                    <div className="text-sm text-gray-700 whitespace-pre-line">{reply.content}</div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* 回复输入区 */}
                          {replyingTo === item.id && (
                            <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <textarea
                                value={replyContent}
                                onChange={(e) => setReplyContent(e.target.value)}
                                placeholder="输入您的回复..."
                                rows={3}
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none"
                              ></textarea>
                              <div className="flex items-center justify-end gap-2 mt-2">
                                <button
                                  onClick={cancelReply}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                                >
                                  取消
                                </button>
                                <button
                                  onClick={() => submitReply(item.id)}
                                  disabled={!replyContent.trim()}
                                  className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 rounded-md hover:bg-teal-700 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  发送回复
                                </button>
                              </div>
                            </div>
                          )}

                          <div className="flex items-center gap-3 mt-2">
                            <span className="text-xs text-gray-400">{item.time}</span>
                            {item.status === 'pending' && replyingTo !== item.id && (
                              <>
                                <button 
                                  onClick={() => startReply(item.id)}
                                  className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap"
                                >
                                  回复
                                </button>
                                <button 
                                  onClick={() => { void viewAIAnswer(item); }}
                                  className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap"
                                >
                                  查看AI回答
                                </button>
                              </>
                            )}
                            <button
                              onClick={() => toggleQuestion(item.id)}
                              className="text-xs text-gray-500 hover:text-gray-700 cursor-pointer whitespace-nowrap"
                            >
                              {expandedQuestions.includes(item.id) ? '收起' : '展开详情'}
                            </button>
                          </div>

                          {/* 展开的详细内容 */}
                          {expandedQuestions.includes(item.id) && (
                            <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <div className="text-xs text-gray-600 mb-2">完整问题内容：</div>
                              <div className="text-sm text-gray-800">{item.question}</div>
                              <div className="mt-3 pt-3 border-t border-gray-200">
                                <div className="text-xs text-gray-600 mb-1">学生信息：{item.student} · 提问时间：{item.time}</div>
                                <div className="text-xs text-gray-600">AI置信度：{item.confidence === 'low' ? '低（建议人工介入）' : '中（可参考AI回答）'}</div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white rounded-lg border border-gray-200">
                <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900">班级讨论区</h2>
                  <button 
                    onClick={() => setShowNewDiscussionModal(true)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-add-line mr-1"></i>发起讨论
                  </button>
                </div>
                <div className="divide-y divide-gray-100">
                  {getSortedDiscussions().length === 0 && (
                    <TeacherCourseEmptyState
                      icon="ri-discuss-line"
                      title="暂无班级讨论"
                      description="当前班级还没有讨论帖，教师或学生发起讨论后会显示在这里。"
                    />
                  )}
                  {getSortedDiscussions().map((discussion) => (
                    <div key={discussion.id} className="px-5 py-4 hover:bg-gray-50">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-medium flex-shrink-0">
                          {discussion.student[0]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-gray-900">{discussion.student}</span>
                            {discussion.pinned && (
                              <span className="px-2 py-0.5 text-xs font-medium bg-orange-50 text-orange-600 rounded-full flex items-center gap-1">
                                <i className="ri-pushpin-fill"></i>置顶
                              </span>
                            )}
                          </div>
                          
                          {/* 讨论标题 */}
                          <div 
                            onClick={() => toggleDiscussion(discussion.id)}
                            className="text-sm font-medium text-gray-900 mb-2 cursor-pointer hover:text-teal-600"
                          >
                            {discussion.title}
                          </div>

                          {/* 展开的讨论内容 */}
                          {expandedDiscussions.includes(discussion.id) && (
                            <div className="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                                {discussion.content}
                              </div>
                            </div>
                          )}

                          {/* 回复列表 */}
                          {expandedDiscussions.includes(discussion.id) && discussion.replies.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {discussion.replies.map((reply, idx) => (
                                <div key={idx} className={`flex items-start gap-2 p-3 rounded-lg border ${
                                  reply.isTeacher 
                                    ? 'bg-teal-50 border-teal-100' 
                                    : 'bg-gray-50 border-gray-200'
                                }`}>
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 ${
                                    reply.isTeacher ? 'bg-teal-500' : 'bg-blue-500'
                                  }`}>
                                    {reply.author[0]}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs font-medium text-gray-900">{reply.author}</span>
                                      {reply.isTeacher && (
                                        <span className="px-1.5 py-0.5 text-xs font-medium bg-teal-100 text-teal-700 rounded">教师</span>
                                      )}
                                      <span className="text-xs text-gray-400">{reply.time}</span>
                                    </div>
                                    <div className="text-sm text-gray-700 whitespace-pre-line">{reply.content}</div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* 回复输入区 */}
                          {expandedDiscussions.includes(discussion.id) && replyingToDiscussion === discussion.id && (
                            <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <textarea
                                value={discussionReplyContent}
                                onChange={(e) => setDiscussionReplyContent(e.target.value)}
                                placeholder="输入您的回复..."
                                rows={3}
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none"
                              ></textarea>
                              <div className="flex items-center justify-end gap-2 mt-2">
                                <button
                                  onClick={cancelReplyDiscussion}
                                  className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                                >
                                  取消
                                </button>
                                <button
                                  onClick={() => submitDiscussionReply(discussion.id)}
                                  disabled={!discussionReplyContent.trim()}
                                  className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 rounded-md hover:bg-teal-700 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  发送回复
                                </button>
                              </div>
                            </div>
                          )}

                          {/* 操作按钮 */}
                          <div className="flex items-center gap-3 mt-2">
                            <span className="text-xs text-gray-400">{discussion.time}</span>
                            <button 
                              onClick={() => toggleLikeDiscussion(discussion.id)}
                              className={`text-xs cursor-pointer whitespace-nowrap flex items-center gap-1 ${
                                discussion.liked ? 'text-teal-600' : 'text-gray-600 hover:text-gray-700'
                              }`}
                            >
                              <i className={`${discussion.liked ? 'ri-thumb-up-fill' : 'ri-thumb-up-line'}`}></i>
                              {discussion.likes}
                            </button>
                            <button 
                              onClick={() => toggleDiscussion(discussion.id)}
                              className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap"
                            >
                              <i className="ri-chat-3-line mr-1"></i>
                              {discussion.replies.length} 条回复
                            </button>
                            {expandedDiscussions.includes(discussion.id) && replyingToDiscussion !== discussion.id && (
                              <button 
                                onClick={() => startReplyDiscussion(discussion.id)}
                                className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap"
                              >
                                回复
                              </button>
                            )}
                            <button 
                              onClick={() => togglePinDiscussion(discussion.id)}
                              className={`text-xs cursor-pointer whitespace-nowrap ${
                                discussion.pinned ? 'text-orange-600' : 'text-gray-600 hover:text-gray-700'
                              }`}
                            >
                              <i className={`${discussion.pinned ? 'ri-pushpin-fill' : 'ri-pushpin-line'} mr-1`}></i>
                              {discussion.pinned ? '取消置顶' : '置顶'}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* AI回答查看弹窗 */}
          {showAIAnswerModal && currentAIAnswer && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">AI回答</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  {isAIAnswerLoading && (
                    <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                      正在加载 AI 回答...
                    </div>
                  )}

                  {aiAnswerError && (
                    <div className="mb-4 rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                      {aiAnswerError}
                    </div>
                  )}

                  {/* 问题 */}
                  <div className="mb-5">
                    <div className="text-xs text-gray-500 mb-2">学生提问：</div>
                    <div className="text-sm font-medium text-gray-900 p-3 bg-gray-50 rounded-lg border border-gray-200">
                      {currentAIAnswer.question}
                    </div>
                  </div>

                  {/* AI置信度 */}
                  <div className="mb-5">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-gray-500">AI回答置信度</span>
                      <span className="text-sm font-semibold text-gray-900">{currentAIAnswer.confidence}%</span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${
                          currentAIAnswer.confidence >= 70 ? 'bg-green-500' :
                          currentAIAnswer.confidence >= 50 ? 'bg-yellow-500' :
                          'bg-red-500'
                        }`}
                        style={{ width: `${currentAIAnswer.confidence}%` }}
                      ></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {currentAIAnswer.confidence >= 70 ? '置信度高，建议采纳' :
                       currentAIAnswer.confidence >= 50 ? '置信度中等，建议审核后采纳' :
                       '置信度低，建议人工回答'}
                    </div>
                  </div>

                  {/* AI回答内容 */}
                  <div className="mb-5">
                    <div className="text-xs text-gray-500 mb-2">AI回答内容：</div>
                    <div className="text-sm text-gray-800 p-4 bg-teal-50 rounded-lg border border-teal-100 whitespace-pre-line leading-relaxed">
                      {currentAIAnswer.aiAnswer}
                    </div>
                  </div>

                  {/* 引用来源 */}
                  {currentAIAnswer.sources.length > 0 && (
                    <div>
                      <div className="text-xs text-gray-500 mb-2">引用来源：</div>
                      <div className="space-y-2">
                        {currentAIAnswer.sources.map((source, idx) => (
                          <div key={idx} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg border border-gray-200">
                            <i className="ri-file-pdf-line text-red-500 text-base"></i>
                            <span className="text-sm text-gray-700">{source.name}</span>
                            {source.page > 0 && (
                              <span className="text-xs text-teal-600">第 {source.page} 页</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowAIAnswerModal(false);
                      setCurrentAIAnswer(null);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                  <button
                    onClick={replyManually}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                  >
                    自行回复
                  </button>
                  <button
                    onClick={() => { void adoptAIAnswer(); }}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    采纳AI回答并发布
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 上传资料弹窗 */}
          {showUploadModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">上传课程资料</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  {/* 拖拽上传区域 */}
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                      isDragging 
                        ? 'border-teal-500 bg-teal-50' 
                        : 'border-gray-300 hover:border-teal-400 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex flex-col items-center">
                      <div className="w-16 h-16 flex items-center justify-center rounded-full bg-teal-50 mb-3">
                        <i className="ri-upload-cloud-line text-teal-600 text-3xl"></i>
                      </div>
                      <div className="text-sm font-medium text-gray-900 mb-1">
                        拖拽文件到此处，或点击选择文件
                      </div>
                      <div className="text-xs text-gray-500">
                        支持 PDF、PPT、Word、视频等格式，单个文件不超过 500MB
                      </div>
                    </div>
                  </div>
                  
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                    accept=".pdf,.ppt,.pptx,.doc,.docx,.mp4,.avi,.mov"
                  />

                  {/* 已选文件列表 */}
                  {uploadFiles.length > 0 && (
                    <div className="mt-5">
                      <div className="text-sm font-semibold text-gray-900 mb-3">
                        已选择 {uploadFiles.length} 个文件
                      </div>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {uploadFiles.map((file, index) => {
                          const fileInfo = getFileIcon(file.name);
                          const progress = uploadProgress[file.name] || 0;
                          
                          return (
                            <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <div className={`w-10 h-10 flex items-center justify-center rounded-lg flex-shrink-0 ${fileInfo.bg}`}>
                                <i className={`${fileInfo.icon} ${fileInfo.color} text-lg`}></i>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-gray-900 truncate">{file.name}</div>
                                <div className="text-xs text-gray-500 mt-1">{formatFileSize(file.size)}</div>
                                {isUploading && progress > 0 && (
                                  <div className="mt-2">
                                    <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                                      <span>上传中...</span>
                                      <span>{progress}%</span>
                                    </div>
                                    <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                      <div 
                                        className="h-full bg-teal-500 rounded-full transition-all duration-300"
                                        style={{ width: `${progress}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                )}
                              </div>
                              {!isUploading && (
                                <button
                                  onClick={() => removeFile(index)}
                                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-red-600 cursor-pointer flex-shrink-0"
                                >
                                  <i className="ri-close-line text-lg"></i>
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowUploadModal(false);
                      setUploadFiles([]);
                      setUploadProgress({});
                    }}
                    disabled={isUploading}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleUpload}
                    disabled={uploadFiles.length === 0 || isUploading}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isUploading ? '上传中...' : `确认上传 (${uploadFiles.length})`}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 发布通知弹窗 */}
          {showNoticeModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">发布通知</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">通知标题 *</label>
                      <input
                        type="text"
                        value={noticeForm.title}
                        onChange={(e) => setNoticeForm({ ...noticeForm, title: e.target.value })}
                        placeholder="请输入通知标题"
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">通知内容 *</label>
                      <textarea
                        rows={6}
                        value={noticeForm.content}
                        onChange={(e) => setNoticeForm({ ...noticeForm, content: e.target.value })}
                        placeholder="请输入通知内容..."
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      ></textarea>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">重要程度</label>
                        <select
                          value={noticeForm.importance}
                          onChange={(e) => setNoticeForm({ ...noticeForm, importance: e.target.value })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
                        >
                          <option value="normal">普通</option>
                          <option value="important">重要</option>
                          <option value="urgent">紧急</option>
                        </select>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">发送范围</label>
                        <select
                          value={noticeForm.scope}
                          onChange={(e) => setNoticeForm({ ...noticeForm, scope: e.target.value })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
                        >
                          <option value="all">全班学生</option>
                          <option value="group1">第1组</option>
                          <option value="group2">第2组</option>
                          <option value="group3">第3组</option>
                        </select>
                      </div>
                    </div>

                    {/* 附件上传区域 */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">附件</label>
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                        <input
                          ref={noticeAttachmentRef}
                          type="file"
                          multiple
                          onChange={(e) => handleAttachmentUpload(e, 'notice')}
                          className="hidden"
                        />
                        <button
                          onClick={() => noticeAttachmentRef.current?.click()}
                          className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                        >
                          <i className="ri-attachment-line mr-1"></i>添加附件
                        </button>
                        <p className="text-xs text-gray-500 mt-2">支持PDF、Word、Excel、图片等格式</p>
                      </div>
                      
                      {/* 附件列表 */}
                      {noticeForm.attachments.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {noticeForm.attachments.map((file, index) => (
                            <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                              <i className="ri-file-line text-gray-400"></i>
                              <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                              <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
                              <button
                                onClick={() => removeAttachment(index, 'notice')}
                                className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-600 cursor-pointer"
                              >
                                <i className="ri-close-line"></i>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowNoticeModal(false);
                      setNoticeForm(createEmptyNoticeForm());
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button
                    onClick={handlePublishNotice}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    确认发布
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 创建作业弹窗 */}
          {showHomeworkModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">创建作业</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">作业标题 *</label>
                        <input
                          type="text"
                          value={homeworkForm.title}
                          onChange={(e) => setHomeworkForm({ ...homeworkForm, title: e.target.value })}
                          placeholder="例如：第3章课后习题"
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">截止时间 *</label>
                        <input
                          type="datetime-local"
                          value={homeworkForm.deadline}
                          onChange={(e) => setHomeworkForm({ ...homeworkForm, deadline: e.target.value })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="allowLate"
                        checked={homeworkForm.allowLate}
                        onChange={(e) => setHomeworkForm({ ...homeworkForm, allowLate: e.target.checked })}
                        className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500"
                      />
                      <label htmlFor="allowLate" className="text-sm text-gray-700 cursor-pointer">允许迟交（扣分）</label>
                    </div>
                    
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <label className="block text-sm font-medium text-gray-700">题目列表 *</label>
                        <button
                          onClick={addHomeworkQuestion}
                          className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                        >
                          <i className="ri-add-line mr-1"></i>添加题目
                        </button>
                      </div>
                      
                      <div className="space-y-3 max-h-96 overflow-y-auto">
                        {homeworkForm.questions.map((question, index) => (
                          <div key={index} className="p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-sm font-medium text-gray-900">第 {index + 1} 题</span>
                              {homeworkForm.questions.length > 1 && (
                                <button
                                  onClick={() => removeHomeworkQuestion(index)}
                                  className="text-xs text-red-600 hover:text-red-700 cursor-pointer whitespace-nowrap"
                                >
                                  <i className="ri-delete-bin-line mr-1"></i>删除
                                </button>
                              )}
                            </div>
                            <div className="space-y-2">
                              <textarea
                                rows={2}
                                value={question.description}
                                onChange={(e) => {
                                  const newQuestions = [...homeworkForm.questions];
                                  newQuestions[index].description = e.target.value;
                                  setHomeworkForm({ ...homeworkForm, questions: newQuestions });
                                }}
                                placeholder="请输入题目描述..."
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                              ></textarea>
                              <input
                                type="text"
                                value={question.answer}
                                onChange={(e) => {
                                  const newQuestions = [...homeworkForm.questions];
                                  newQuestions[index].answer = e.target.value;
                                  setHomeworkForm({ ...homeworkForm, questions: newQuestions });
                                }}
                                placeholder="参考答案（选填）"
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* 附件上传区域 */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">作业附件</label>
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                        <input
                          ref={homeworkAttachmentRef}
                          type="file"
                          multiple
                          onChange={(e) => handleAttachmentUpload(e, 'homework')}
                          className="hidden"
                        />
                        <button
                          onClick={() => homeworkAttachmentRef.current?.click()}
                          className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                        >
                          <i className="ri-attachment-line mr-1"></i>添加附件
                        </button>
                        <p className="text-xs text-gray-500 mt-2">可上传作业说明文档、参考资料等</p>
                      </div>
                      
                      {/* 附件列表 */}
                      {homeworkForm.attachments.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {homeworkForm.attachments.map((file, index) => (
                            <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                              <i className="ri-file-line text-gray-400"></i>
                              <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                              <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
                              <button
                                onClick={() => removeAttachment(index, 'homework')}
                                className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-600 cursor-pointer"
                              >
                                <i className="ri-close-line"></i>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowHomeworkModal(false);
                      setHomeworkForm(createEmptyHomeworkForm());
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleCreateHomework}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    确认发布
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 创建考试弹窗 */}
          {showExamModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">创建考试</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">考试名称 *</label>
                      <input
                        type="text"
                        value={examForm.name}
                        onChange={(e) => setExamForm({ ...examForm, name: e.target.value })}
                        placeholder="例如：期中考试"
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">开始时间 *</label>
                        <input
                          type="datetime-local"
                          value={examForm.startTime}
                          onChange={(e) => setExamForm({ ...examForm, startTime: e.target.value })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">结束时间 *</label>
                        <input
                          type="datetime-local"
                          value={examForm.endTime}
                          onChange={(e) => setExamForm({ ...examForm, endTime: e.target.value })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        答题时长限制（分钟）
                        <span className="ml-2 text-xs font-normal text-gray-400">学生开始答题后可用的最大时间</span>
                      </label>
                      <div className="flex items-center gap-3">
                        <input
                          type="number"
                          min={10}
                          max={300}
                          value={examForm.duration}
                          onChange={(e) => setExamForm({ ...examForm, duration: parseInt(e.target.value) || 90 })}
                          className="w-40 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                        <span className="text-sm text-gray-500">分钟</span>
                        <div className="flex items-center gap-2 ml-2">
                          {[30, 60, 90, 120].map(min => (
                            <button
                              key={min}
                              type="button"
                              onClick={() => setExamForm({ ...examForm, duration: min })}
                              className={`px-3 py-1.5 text-xs font-medium rounded-lg border cursor-pointer whitespace-nowrap transition-colors ${examForm.duration === min ? 'bg-teal-100 text-teal-700 border-teal-300' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'}`}
                            >
                              {min}分钟
                            </button>
                          ))}
                        </div>
                      </div>
                      {examForm.startTime && examForm.endTime && (() => {
                        const diffMs = new Date(examForm.endTime).getTime() - new Date(examForm.startTime).getTime();
                        const diffMin = Math.round(diffMs / 60000);
                        if (diffMin > 0 && examForm.duration > diffMin) {
                          return (
                            <p className="mt-1.5 text-xs text-orange-500 flex items-center gap-1">
                              <i className="ri-alert-line"></i>
                              答题时长超过了考试窗口（{diffMin}分钟），建议调整为不超过考试窗口的时长
                            </p>
                          );
                        }
                        return null;
                      })()}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">总分</label>
                        <input
                          type="number"
                          value={examForm.totalScore}
                          onChange={(e) => setExamForm({ ...examForm, totalScore: parseInt(e.target.value) || 100 })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">题目数量</label>
                        <input
                          type="number"
                          value={examForm.questionCount}
                          onChange={(e) => setExamForm({ ...examForm, questionCount: parseInt(e.target.value) || 10 })}
                          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>
                    
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <label className="block text-sm font-medium text-gray-700">AI智能组卷</label>
                        <button
                          onClick={handleGenerateQuestions}
                          disabled={isGeneratingQuestions}
                          className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isGeneratingQuestions ? (
                            <>
                              <i className="ri-loader-4-line animate-spin mr-1"></i>生成中...
                            </>
                          ) : (
                            <>
                              <i className="ri-ai-generate mr-1"></i>生成试卷
                            </>
                          )}
                        </button>
                      </div>
                      
                      {examForm.generatedQuestions.length > 0 && (
                        <div className="border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
                          <div className="space-y-3">
                            {examForm.generatedQuestions.map((q, index) => (
                              <div key={index} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                                <div className="flex-shrink-0">
                                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-purple-100 text-purple-600 text-xs font-medium">
                                    {index + 1}
                                  </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="px-2 py-0.5 text-xs font-medium text-purple-600 bg-purple-50 rounded">
                                      {q.type}
                                    </span>
                                    <span className="text-xs text-gray-500">{q.score}分</span>
                                  </div>
                                  <div className="text-sm text-gray-700">{q.content}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {examForm.generatedQuestions.length === 0 && !isGeneratingQuestions && (
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                          <i className="ri-file-list-3-line text-4xl text-gray-300 mb-2"></i>
                          <p className="text-sm text-gray-500">点击"生成试卷"按钮，AI将根据课程知识库智能组卷</p>
                        </div>
                      )}
                    </div>

                    {/* 附件上传区域 */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">考试附件</label>
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                        <input
                          ref={examAttachmentRef}
                          type="file"
                          multiple
                          onChange={(e) => handleAttachmentUpload(e, 'exam')}
                          className="hidden"
                        />
                        <button
                          onClick={() => examAttachmentRef.current?.click()}
                          className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                        >
                          <i className="ri-attachment-line mr-1"></i>添加附件
                        </button>
                        <p className="text-xs text-gray-500 mt-2">可上传考试说明、答题卡等文件</p>
                      </div>
                      
                      {/* 附件列表 */}
                      {examForm.attachments.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {examForm.attachments.map((file, index) => (
                            <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                              <i className="ri-file-line text-gray-400"></i>
                              <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                              <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
                              <button
                                onClick={() => removeAttachment(index, 'exam')}
                                className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-600 cursor-pointer"
                              >
                                <i className="ri-close-line"></i>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowExamModal(false);
                      setExamForm(createEmptyExamForm());
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleCreateExam}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    确认发布
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 任务详情弹窗 */}
          {showTaskDetailModal && currentTask && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">任务详情</h2>
                  <button
                    onClick={() => setShowTaskDetailModal(false)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  <div className="space-y-5">
                    {isTaskDetailLoading && (
                      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                        正在加载任务详情...
                      </div>
                    )}

                    {taskDetailError && (
                      <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                        {taskDetailError}
                      </div>
                    )}

                    <div>
                      <div className="flex items-center gap-3 mb-4">
                        <div className={`w-12 h-12 flex items-center justify-center rounded-lg ${
                          currentTask.type === 'homework' ? 'bg-green-50' : 
                          currentTask.type === 'exam' ? 'bg-purple-50' : 'bg-blue-50'
                        }`}>
                          <i className={`text-xl ${
                            currentTask.type === 'homework' ? 'ri-file-text-line text-green-600' : 
                            currentTask.type === 'exam' ? 'ri-file-list-line text-purple-600' : 
                            'ri-notification-line text-blue-600'
                          }`}></i>
                        </div>
                        <div className="flex-1">
                          <h3 className="text-base font-semibold text-gray-900">{currentTask.title}</h3>
                          <div className="flex items-center gap-3 mt-1">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              currentTask.status === '进行中' ? 'bg-blue-50 text-blue-600' : 
                              currentTask.status === '未开始' ? 'bg-gray-100 text-gray-600' : 
                              currentTask.status === '已结束' ? 'bg-gray-100 text-gray-500' : 
                              'bg-green-50 text-green-600'
                            }`}>{currentTask.status}</span>
                            <span className="text-xs text-gray-500">发布于 {currentTask.publishDate}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="text-sm font-semibold text-gray-900 mb-2">任务说明</div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-700">
                        {currentTask.description}
                      </div>
                    </div>

                    {currentTask.requirements.length > 0 && (
                      <div>
                        <div className="text-sm font-semibold text-gray-900 mb-2">任务要求</div>
                        <div className="space-y-2">
                          {currentTask.requirements.map((item, index) => (
                            <div key={index} className="flex items-start gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2">
                              <i className="ri-checkbox-circle-line text-teal-600 mt-0.5"></i>
                              <span className="text-sm text-gray-700">{item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                      {currentTask.type === 'exam' && (currentTask as any).startTime && (
                        <div>
                          <div className="text-xs text-gray-500 mb-1">考试开始时间</div>
                          <div className="text-sm font-medium text-gray-900">{(currentTask as any).startTime}</div>
                        </div>
                      )}
                      {currentTask.deadline !== '-' && (
                        <div>
                          <div className="text-xs text-gray-500 mb-1">{currentTask.type === 'exam' ? '考试结束时间' : '截止时间'}</div>
                          <div className="text-sm font-medium text-gray-900">{currentTask.deadline}</div>
                        </div>
                      )}
                      {currentTask.type === 'exam' && (currentTask as any).duration && (
                        <div>
                          <div className="text-xs text-gray-500 mb-1">答题时长限制</div>
                          <div className="text-sm font-medium text-teal-700">{(currentTask as any).duration} 分钟</div>
                        </div>
                      )}
                      {currentTask.type !== 'notice' && (
                        <div>
                          <div className="text-xs text-gray-500 mb-1">提交情况</div>
                          <div className="text-sm font-medium text-gray-900">
                            {currentTask.submitted}/{currentTask.total} 
                            <span className="text-xs text-gray-500 ml-1">
                              ({Math.round((currentTask.submitted / currentTask.total) * 100)}%)
                            </span>
                          </div>
                        </div>
                      )}
                    </div>

                    {currentTask.attachments.length > 0 && (
                      <div>
                        <div className="text-sm font-semibold text-gray-900 mb-2">附件</div>
                        <div className="space-y-2">
                          {currentTask.attachments.map((filename: string, index: number) => (
                            <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                              <i className="ri-file-line text-gray-400 text-lg"></i>
                              <span className="flex-1 text-sm text-gray-700">{filename}</span>
                              <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">
                                <i className="ri-download-line mr-1"></i>下载
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {currentTask.type !== 'notice' && (
                      <div>
                        <div className="text-sm font-semibold text-gray-900 mb-2">提交统计</div>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="p-3 bg-green-50 rounded-lg border border-green-100">
                            <div className="text-xs text-green-600 mb-1">已提交</div>
                            <div className="text-lg font-bold text-green-600">{currentTask.submitted}</div>
                          </div>
                          <div className="p-3 bg-orange-50 rounded-lg border border-orange-100">
                            <div className="text-xs text-orange-600 mb-1">未提交</div>
                            <div className="text-lg font-bold text-orange-600">{currentTask.total - currentTask.submitted}</div>
                          </div>
                          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="text-xs text-gray-600 mb-1">提交率</div>
                            <div className="text-lg font-bold text-gray-900">
                              {Math.round((currentTask.submitted / currentTask.total) * 100)}%
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {currentTask.type !== 'notice' && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm font-semibold text-gray-900">学生情况</div>
                          <div className="text-xs text-gray-400">
                            共 {currentTask.participantCount} 人
                          </div>
                        </div>

                        {currentTask.submissions.length > 0 ? (
                          <div className="overflow-hidden rounded-lg border border-gray-200">
                            <div className="grid grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 bg-gray-50 px-4 py-3 text-xs font-medium text-gray-500">
                              <span>学生</span>
                              <span>分组</span>
                              <span>提交状态</span>
                              <span>成绩/时间</span>
                            </div>
                            <div className="divide-y divide-gray-100">
                              {currentTask.submissions.map((submission) => {
                                const submissionMeta = getTaskSubmissionStatusMeta(submission.status);

                                return (
                                  <div key={submission.id} className="grid grid-cols-[1.4fr_1fr_1fr_1fr] gap-3 px-4 py-3 text-sm text-gray-700">
                                    <div>
                                      <div className="font-medium text-gray-900">{submission.studentName}</div>
                                      <div className="text-xs text-gray-400">{submission.studentId}</div>
                                    </div>
                                    <div className="text-sm text-gray-600">{submission.groupName}</div>
                                    <div>
                                      <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${submissionMeta.className}`}>
                                        {submissionMeta.label}
                                      </span>
                                    </div>
                                    <div className="text-sm text-gray-600">
                                      {submission.score !== undefined ? (
                                        <span className="font-medium text-gray-900">{submission.score} 分</span>
                                      ) : (
                                        <span>{submission.submittedAt}</span>
                                      )}
                                      {submission.score !== undefined && submission.submittedAt !== '-' && (
                                        <div className="text-xs text-gray-400 mt-0.5">{submission.submittedAt}</div>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : (
                          <div className="rounded-lg border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500">
                            暂无学生提交详情，后续可直接对接后端任务详情接口返回的提交记录。
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between flex-shrink-0">
                  <div className="flex items-center gap-2">
                    {currentTask.status === '进行中' && (
                      <button
                        onClick={async () => {
                          await updateTaskStatus(currentTask.id, '已结束');
                          setShowTaskDetailModal(false);
                        }}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                      >
                        结束任务
                      </button>
                    )}
                    {currentTask.status === '未开始' && (
                      <button
                        onClick={async () => {
                          await updateTaskStatus(currentTask.id, '进行中');
                          setShowTaskDetailModal(false);
                        }}
                        className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                      >
                        开始任务
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setShowTaskDetailModal(false)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'students' && (
            <div className="max-w-6xl mx-auto">
              <div className="flex items-center justify-between mb-6">
                <h1 className="text-xl font-bold text-gray-900">学生管理</h1>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setShowGroupManageModal(true)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-group-line mr-1"></i>管理分组
                  </button>
                  <button
                    onClick={() => setShowExportModal(true)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-download-line mr-1"></i>导出
                  </button>
                </div>
              </div>

              {/* 统计卡片 */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">学生总数</span>
                    <i className="ri-group-line text-blue-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{students.length}</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">平均进度</span>
                    <i className="ri-line-chart-line text-green-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {averageStudentProgress}%
                  </div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">预警学生</span>
                    <i className="ri-alert-line text-orange-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {students.filter(s => s.status === 'warning').length}
                  </div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-600">平均出勤率</span>
                    <i className="ri-calendar-check-line text-purple-600 text-lg"></i>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">
                    {averageStudentAttendance}%
                  </div>
                </div>
              </div>

              {/* 搜索和筛选 */}
              <div className="bg-white rounded-lg border border-gray-200 mb-5">
                <div className="px-5 py-4 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setStudentGroupTab('all')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${
                          studentGroupTab === 'all' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        全部学生
                      </button>
                      <button
                        onClick={() => setStudentGroupTab('group1')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${
                          studentGroupTab === 'group1' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        第1组
                      </button>
                      <button
                        onClick={() => setStudentGroupTab('group2')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${
                          studentGroupTab === 'group2' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        第2组
                      </button>
                      <button
                        onClick={() => setStudentGroupTab('group3')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${
                          studentGroupTab === 'group3' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        第3组
                      </button>
                      <button
                        onClick={() => setStudentGroupTab('warning')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer whitespace-nowrap ${
                          studentGroupTab === 'warning' ? 'bg-orange-50 text-orange-600' : 'text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        <i className="ri-alert-line mr-1"></i>预警名单
                      </button>
                    </div>
                    <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
                      <i className="ri-search-line text-gray-400 text-sm"></i>
                      <input
                        type="text"
                        value={studentSearchQuery}
                        onChange={(e) => setStudentSearchQuery(e.target.value)}
                        placeholder="搜索姓名或学号..."
                        className="bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none w-48"
                      />
                    </div>
                  </div>
                </div>

                {/* 学生列表表格 */}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">姓名</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">学号</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">分组</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">学习进度</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">作业完成</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">出勤率</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">状态</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {getFilteredStudents().length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-5 py-12 text-center">
                            <div className="flex flex-col items-center justify-center text-gray-400">
                              <i className="ri-user-search-line text-4xl mb-2"></i>
                              <div className="text-sm">未找到匹配的学生</div>
                            </div>
                          </td>
                        </tr>
                      ) : (
                        getFilteredStudents().map((student) => (
                          <tr 
                            key={student.id} 
                            className={`hover:bg-gray-50 ${student.status === 'warning' ? 'bg-orange-50/30' : ''}`}
                          >
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-medium">
                                  {student.name[0]}
                                </div>
                                <span className="text-sm font-medium text-gray-900">{student.name}</span>
                              </div>
                            </td>
                            <td className="px-5 py-4 text-sm text-gray-600">{student.studentId}</td>
                            <td className="px-5 py-4">
                              <span className="px-2 py-1 text-xs font-medium bg-blue-50 text-blue-600 rounded-full">
                                第{student.group}组
                              </span>
                            </td>
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden max-w-[80px]">
                                  <div 
                                    className={`h-full rounded-full ${
                                      student.progress >= 80 ? 'bg-green-500' :
                                      student.progress >= 60 ? 'bg-yellow-500' :
                                      'bg-red-500'
                                    }`}
                                    style={{ width: `${student.progress}%` }}
                                  ></div>
                                </div>
                                <span className="text-xs font-medium text-gray-700">{student.progress}%</span>
                              </div>
                            </td>
                            <td className="px-5 py-4 text-sm text-gray-600">{student.homework}/15</td>
                            <td className="px-5 py-4 text-sm text-gray-600">{student.attendance}%</td>
                            <td className="px-5 py-4">
                              {student.status === 'warning' ? (
                                <div className="flex flex-col gap-1">
                                  <span className="px-2 py-1 text-xs font-medium bg-orange-100 text-orange-600 rounded-full inline-flex items-center gap-1 w-fit">
                                    <i className="ri-alert-line"></i>预警
                                  </span>
                                  <span className="text-xs text-orange-600">{student.warningReason}</span>
                                </div>
                              ) : (
                                <span className="px-2 py-1 text-xs font-medium bg-green-50 text-green-600 rounded-full">
                                  正常
                                </span>
                              )}
                            </td>
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-2">
                                <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">
                                  查看详情
                                </button>
                                {student.status === 'warning' && (
                                  <button 
                                    onClick={() => handleSendWarningReminder(student.id)}
                                    className="text-xs text-orange-600 hover:text-orange-700 cursor-pointer whitespace-nowrap"
                                  >
                                    发送提醒
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'ai' && (
            <div className="h-[calc(100vh-7rem)] min-h-[680px]">
              <TeacherAIAssistant />
            </div>
          )}

          {/* 预览文件弹窗 */}
          {showPreviewModal && currentFile && currentFilePreview && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">预览 - {currentFile.name}</h2>
                  <button
                    onClick={() => setShowPreviewModal(false)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="space-y-4">
                    {isFilePreviewLoading && (
                      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                        正在加载文件预览...
                      </div>
                    )}

                    {filePreviewError && (
                      <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                        {filePreviewError}
                      </div>
                    )}

                    <div className="grid grid-cols-3 gap-4">
                      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                        <div className="text-xs text-gray-500 mb-1">预览类型</div>
                        <div className="text-sm font-medium text-gray-900">
                          {currentFilePreview.previewType === 'video'
                            ? '视频'
                            : currentFilePreview.previewType === 'slide'
                              ? '幻灯片'
                              : '文档'}
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                        <div className="text-xs text-gray-500 mb-1">页数 / 时长</div>
                        <div className="text-sm font-medium text-gray-900">
                          {currentFilePreview.pageCount
                            ? `${currentFilePreview.pageCount} 页`
                            : currentFilePreview.durationText ?? '待返回'}
                        </div>
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                        <div className="text-xs text-gray-500 mb-1">下载次数</div>
                        <div className="text-sm font-medium text-gray-900">{currentFile.downloads} 次</div>
                      </div>
                    </div>

                    {currentFilePreview.previewType === 'video' && currentFilePreview.previewUrl ? (
                      <video controls className="w-full rounded-lg bg-black">
                        <source src={currentFilePreview.previewUrl} />
                      </video>
                    ) : currentFilePreview.previewUrl ? (
                      <iframe
                        title={`preview-${currentFile.id}`}
                        src={currentFilePreview.previewUrl}
                        className="h-[520px] w-full rounded-lg border border-gray-200 bg-white"
                      />
                    ) : (
                      <div className="border border-gray-200 rounded-lg p-8 bg-gray-50 min-h-[420px] flex items-center justify-center">
                        <div className="text-center text-gray-400">
                          <i className={`${currentFile.type === 'PDF' ? 'ri-file-pdf-line' : currentFile.type === 'PPT' ? 'ri-file-ppt-line' : 'ri-video-line'} text-6xl mb-3`}></i>
                          <div className="text-sm">
                            {currentFilePreview.previewType === 'video' ? '视频预览待后端返回播放地址' : `${currentFile.type} 文档预览待返回`}
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-600">
                      {currentFilePreview.note}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => { void handleDownloadFile(currentFile); }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={downloadingFileId === currentFile.id}
                  >
                    <i className="ri-download-line mr-1"></i>{downloadingFileId === currentFile.id ? '下载中...' : '下载'}
                  </button>
                  <button
                    onClick={() => setShowPreviewModal(false)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* AI解析弹窗 */}
          {showAIAnalysisModal && currentFile && currentFileAnalysis && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">AI解析 - {currentFile.name}</h2>
                  <button
                    onClick={() => setShowAIAnalysisModal(false)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="space-y-5">
                    {isFileAnalysisLoading && (
                      <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                        正在加载 AI 解析结果...
                      </div>
                    )}

                    {fileAnalysisError && (
                      <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                        {fileAnalysisError}
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs text-gray-500 mb-1">解析状态</div>
                        <div className="text-sm font-medium text-green-600">已生成解析结果</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 mb-1">生成时间</div>
                        <div className="text-sm font-medium text-gray-900">{currentFileAnalysis.generatedAt}</div>
                      </div>
                    </div>

                    <div>
                      <div className="text-sm font-semibold text-gray-900 mb-2">内容摘要</div>
                      <div className="text-sm text-gray-700 leading-relaxed">
                        {currentFileAnalysis.summary}
                      </div>
                    </div>
                    
                    <div>
                      <div className="text-sm font-semibold text-gray-900 mb-2">核心知识点</div>
                      <div className="space-y-2">
                        {currentFileAnalysis.keyPoints.map((point, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm text-gray-700">
                            <i className="ri-checkbox-circle-fill text-teal-500 mt-0.5"></i>
                            <span>{point}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <div>
                      <div className="text-sm font-semibold text-gray-900 mb-2">难点分析</div>
                      <div className="space-y-2">
                        {currentFileAnalysis.difficulties.map((item, i) => (
                          <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <span className="text-sm text-gray-700">{item.title}</span>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              item.difficulty === '较难' ? 'bg-orange-100 text-orange-600' : 'bg-yellow-100 text-yellow-600'
                            }`}>{item.difficulty}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <div>
                      <div className="text-sm font-semibold text-gray-900 mb-2">建议学习时长</div>
                      <div className="text-sm text-gray-700">{currentFileAnalysis.recommendedStudyDuration}</div>
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end flex-shrink-0">
                  <button
                    onClick={() => setShowAIAnalysisModal(false)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 重命名弹窗 */}
          {showRenameModal && currentFile && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-md">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">重命名文件</h2>
                </div>
                
                <div className="px-6 py-5">
                  <label className="block text-sm font-medium text-gray-700 mb-2">新文件名</label>
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    placeholder="请输入新文件名"
                  />
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
                  <button
                    onClick={() => {
                      setShowRenameModal(false);
                      setRenameValue('');
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button
                    onClick={confirmRename}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    确认
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 分享弹窗 */}
          {showShareModal && currentFile && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-md">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">分享文件</h2>
                </div>
                
                <div className="px-6 py-5">
                  <div className="mb-4">
                    <div className="text-sm font-medium text-gray-900 mb-2">{currentFile.name}</div>
                    <div className="text-xs text-gray-500">{currentFile.size} · {currentFile.type}</div>
                  </div>
                  
                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <div className="text-xs text-gray-500 mb-2">分享链接</div>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={`https://luoying.edu/share/${currentFile.id}`}
                        readOnly
                        className="flex-1 px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg"
                      />
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(`https://luoying.edu/share/${currentFile.id}`);
                          alert('链接已复制到剪贴板');
                        }}
                        className="px-3 py-2 text-sm font-medium text-teal-600 bg-white border border-teal-600 rounded-lg hover:bg-teal-50 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-file-copy-line mr-1"></i>复制
                      </button>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">分享范围</label>
                    <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer">
                      <option>仅本班学生</option>
                      <option>全校师生</option>
                      <option>公开访问</option>
                    </select>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end">
                  <button
                    onClick={() => setShowShareModal(false)}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 发布新讨论弹窗 */}
          {showNewDiscussionModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <h2 className="text-lg font-semibold text-gray-900">发起讨论</h2>
                </div>
                
                <div className="px-6 py-5 overflow-y-auto flex-1">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">讨论标题 *</label>
                      <input
                        type="text"
                        value={newDiscussionForm.title}
                        onChange={(e) => setNewDiscussionForm({ ...newDiscussionForm, title: e.target.value })}
                        placeholder="请输入讨论标题"
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">讨论内容 *</label>
                      <textarea
                        rows={8}
                        value={newDiscussionForm.content}
                        onChange={(e) => setNewDiscussionForm({ ...newDiscussionForm, content: e.target.value })}
                        placeholder="请输入讨论内容..."
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      ></textarea>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="pinDiscussion"
                        checked={newDiscussionForm.pinned}
                        onChange={(e) => setNewDiscussionForm({ ...newDiscussionForm, pinned: e.target.checked })}
                        className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500"
                      />
                      <label htmlFor="pinDiscussion" className="text-sm text-gray-700 cursor-pointer">置顶此讨论</label>
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                  <button
                    onClick={() => {
                      setShowNewDiscussionModal(false);
                      setNewDiscussionForm(createEmptyDiscussionForm());
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button
                    onClick={handlePublishDiscussion}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    发布讨论
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* 分组管理弹窗 */}
      {showGroupManageModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900">管理分组</h2>
            </div>
            
            <div className="px-6 py-5 overflow-y-auto flex-1">
              <div className="mb-5">
                <div className="text-sm font-medium text-gray-700 mb-3">选择学生并移动到指定分组</div>
                <div className="flex items-center gap-3 mb-4">
                  <select
                    value={targetGroup}
                    onChange={(e) => setTargetGroup(parseInt(e.target.value))}
                    className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
                  >
                    <option value={1}>第1组</option>
                    <option value={2}>第2组</option>
                    <option value={3}>第3组</option>
                  </select>
                  <button
                    onClick={handleMoveStudentsToGroup}
                    disabled={selectedStudents.length === 0}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <i className="ri-arrow-right-line mr-1"></i>移动选中学生
                  </button>
                  <span className="text-sm text-gray-500">
                    已选择 {selectedStudents.length} 名学生
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {[1, 2, 3].map(groupNum => (
                  <div key={groupNum} className="border border-gray-200 rounded-lg">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-gray-900">第{groupNum}组</span>
                        <span className="text-xs text-gray-500">
                          {students.filter(s => s.group === groupNum).length}人
                        </span>
                      </div>
                    </div>
                    <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
                      {students.filter(s => s.group === groupNum).map(student => (
                        <label
                          key={student.id}
                          className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedStudents.includes(student.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedStudents([...selectedStudents, student.id]);
                              } else {
                                setSelectedStudents(selectedStudents.filter(id => id !== student.id));
                              }
                            }}
                            className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500"
                          />
                          <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                            {student.name[0]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-900">{student.name}</div>
                            <div className="text-xs text-gray-500">{student.studentId}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
              <button
                onClick={() => {
                  setShowGroupManageModal(false);
                  setSelectedStudents([]);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 导出弹窗 */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900">导出学生数据</h2>
            </div>
            
            <div className="px-6 py-5 overflow-y-auto flex-1">
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">导出范围</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="export-scope"
                        value="current"
                        checked={exportForm.scope === 'current'}
                        onChange={(e) => setExportForm({ ...exportForm, scope: e.target.value })}
                        className="w-4 h-4 text-teal-600 border-gray-300 focus:ring-teal-500"
                      />
                      <span className="text-sm text-gray-700">当前视图（{getFilteredStudents().length}名学生）</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="export-scope"
                        value="all"
                        checked={exportForm.scope === 'all'}
                        onChange={(e) => setExportForm({ ...exportForm, scope: e.target.value })}
                        className="w-4 h-4 text-teal-600 border-gray-300 focus:ring-teal-500"
                      />
                      <span className="text-sm text-gray-700">全部学生（{students.length}名学生）</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">导出格式</label>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="export-format"
                        value="csv"
                        checked={exportForm.format === 'csv'}
                        onChange={(e) => setExportForm({ ...exportForm, format: e.target.value })}
                        className="w-4 h-4 text-teal-600 border-gray-300 focus:ring-teal-500"
                      />
                      <span className="text-sm text-gray-700">CSV</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="export-format"
                        value="excel"
                        checked={exportForm.format === 'excel'}
                        onChange={(e) => setExportForm({ ...exportForm, format: e.target.value })}
                        className="w-4 h-4 text-teal-600 border-gray-300 focus:ring-teal-500"
                      />
                      <span className="text-sm text-gray-700">Excel</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">导出字段</label>
                  <div className="space-y-2">
                    {[
                      { key: 'name', label: '姓名' },
                      { key: 'studentId', label: '学号' },
                      { key: 'group', label: '分组' },
                      { key: 'progress', label: '学习进度' },
                      { key: 'homework', label: '作业完成情况' },
                      { key: 'attendance', label: '出勤率' }
                    ].map(field => (
                      <label key={field.key} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={exportForm.fields[field.key as keyof typeof exportForm.fields]}
                          onChange={(e) => setExportForm({
                            ...exportForm,
                            fields: { ...exportForm.fields, [field.key]: e.target.checked }
                          })}
                          className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500"
                        />
                        <span className="text-sm text-gray-700">{field.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
              <button
                onClick={() => {
                  setShowExportModal(false);
                  setExportForm(createEmptyExportForm());
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
              >
                取消
              </button>
              <button
                onClick={handleExport}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-download-line mr-1"></i>确认导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
