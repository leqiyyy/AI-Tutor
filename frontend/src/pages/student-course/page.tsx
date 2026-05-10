import { useState, useRef, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import KnowledgeGraphViewer from '@/components/KnowledgeGraphViewer';
import AIAssistant from './components/AIAssistant';
import MyLearning from './components/MyLearning';
import {
  getKnowledgeGraphRootIds,
  normalizeKnowledgeGraph,
} from '@/lib/knowledge-graph';
import { getNameInitial } from '@/lib/display';
import { useCourseBootstrap } from '@/lib/use-course-bootstrap';
import { useAuth } from '@/hooks/use-auth';
import { courseService, downloadCourseFileFromUrl } from '@/services/course';
import { learningService } from '@/services/learning';
import type {
  CourseDiscussion,
  CourseFaq,
  CourseSearchResult,
  KnowledgeGraphEdge,
  KnowledgeGraphNode,
  StudentCourseMaterial,
  StudentCourseHomeData,
  StudentCourseQuestion,
  StudentCourseTask,
  TeacherCourseMaterialAnalysisDetail,
  TeacherCourseMaterialPreviewData,
} from '@/types/course';
import type { Flashcard, FlashcardDeck, LearningMistake, MistakePracticeData } from '@/types/learning';

const EMPTY_STUDENT_HOME: StudentCourseHomeData = {
  welcome: {
    studentName: '',
    weeklyStudyHours: '0小时',
    weeklyGoalRemaining: '0小时',
    courseProgress: 0,
    streakDays: 0,
    homeworkCompleted: '0/0',
    learnedChapters: '0/0',
    aiQuestions: '0次',
  },
  quickActions: [],
  notices: [],
  upcomingTasks: [],
  todayUpdates: [],
  classActivities: [],
  milestones: [],
  progress: {
    percent: 0,
    startDate: '',
    endDate: '',
  },
};

function StudentCourseEmptyState({
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

function normalizeMaterialStatus(status?: string | null) {
  return (status || '').trim().toLowerCase();
}

function isIndexedMaterialStatus(status?: string | null) {
  const normalized = normalizeMaterialStatus(status);
  return ['indexed', 'completed', 'complete', 'success', 'ready', '已解析', '解析完成'].includes(normalized);
}

function isMaterialIndexingStatus(status?: string | null) {
  const normalized = normalizeMaterialStatus(status);
  return ['pending', 'queued', 'processing', 'running', '待解析', '解析中'].includes(normalized);
}

function getMaterialStatusMeta(status?: string | null) {
  const normalized = normalizeMaterialStatus(status);
  if (isIndexedMaterialStatus(status)) {
    return { label: '已解析', className: 'bg-green-50 text-green-600' };
  }
  if (['failed', 'error', '解析失败'].includes(normalized)) {
    return { label: '解析失败', className: 'bg-red-50 text-red-600' };
  }
  if (['partial', 'degraded', '部分完成'].includes(normalized)) {
    return { label: '部分完成', className: 'bg-orange-50 text-orange-600' };
  }
  if (isMaterialIndexingStatus(status)) {
    return { label: '解析中', className: 'bg-yellow-50 text-yellow-600' };
  }
  return { label: status || '待解析', className: 'bg-gray-100 text-gray-600' };
}

function createEmptyMistakeForm() {
  return {
    question: '',
    chapter: '',
    myAnswer: '',
    correctAnswer: '',
    analysis: '',
  };
}

function createEmptyQuestionForm() {
  return {
    title: '',
    content: '',
    attachments: [] as File[],
  };
}

function createEmptyDiscussionForm() {
  return {
    title: '',
    content: '',
  };
}

function createEmptyAiToTeacherForm() {
  return {
    title: '',
    content: '',
    aiAnswer: '',
    reason: '',
  };
}

function createEmptyDeckForm() {
  return {
    name: '',
    cards: [{ front: '', back: '' }],
  };
}

export default function StudentCourse() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState('home');
  const { bootstrap, course, courseError } = useCourseBootstrap(id, 'student');
  const courseId = course?.id ?? id ?? '1';
  const [highlightedTaskId, setHighlightedTaskId] = useState<string | null>(null);
  const [highlightedChapterId, setHighlightedChapterId] = useState<string | null>(null);
  const [studentHome, setStudentHome] = useState<StudentCourseHomeData>(EMPTY_STUDENT_HOME);

  // 新增：课程资料相关状态
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [showAIAnalysisModal, setShowAIAnalysisModal] = useState(false);
  const [showKnowledgeGraphModal, setShowKnowledgeGraphModal] = useState(false);
  const [currentFile, setCurrentFile] = useState<StudentCourseMaterial | null>(null);
  const [currentFilePreview, setCurrentFilePreview] = useState<TeacherCourseMaterialPreviewData | null>(null);
  const [currentFileAnalysis, setCurrentFileAnalysis] = useState<TeacherCourseMaterialAnalysisDetail | null>(null);
  const [filePreviewError, setFilePreviewError] = useState('');
  const [fileAnalysisError, setFileAnalysisError] = useState('');
  const [isFilePreviewLoading, setIsFilePreviewLoading] = useState(false);
  const [isFileAnalysisLoading, setIsFileAnalysisLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<CourseSearchResult[]>([]);
  const [searchError, setSearchError] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [videoSpeed, setVideoSpeed] = useState('1.0');
  const [courseMaterials, setCourseMaterials] = useState<StudentCourseMaterial[]>([]);
  const [graphNodes, setGraphNodes] = useState<KnowledgeGraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<KnowledgeGraphEdge[]>([]);
  const [graphRootIds, setGraphRootIds] = useState<string[]>(['root']);

  // 新增：任务中心相关状态
  const [taskFilter, setTaskFilter] = useState('all');
  const [showHomeworkModal, setShowHomeworkModal] = useState(false);
  const [showGradingModal, setShowGradingModal] = useState(false);
  const [currentHomework, setCurrentHomework] = useState<any>(null);
  const [homeworkAnswers, setHomeworkAnswers] = useState<Record<string, string>>({});
  const [isSubmittingHomework, setIsSubmittingHomework] = useState(false);
  const [showMistakeDetailModal, setShowMistakeDetailModal] = useState(false);
  const [showAddMistakeModal, setShowAddMistakeModal] = useState(false);
  const [currentMistake, setCurrentMistake] = useState<LearningMistake | null>(null);
  const [currentMistakePractice, setCurrentMistakePractice] = useState<MistakePracticeData | null>(null);
  const [mistakeFilter, setMistakeFilter] = useState('all');
  const [newMistakeForm, setNewMistakeForm] = useState(createEmptyMistakeForm);

  // 新增：互动空间相关状态
  const [expandedQuestions, setExpandedQuestions] = useState<number[]>([]);
  const [replyingToQuestion, setReplyingToQuestion] = useState<number | null>(null);
  const [questionReplyContent, setQuestionReplyContent] = useState('');
  const [showAddQuestionModal, setShowAddQuestionModal] = useState(false);
  const [newQuestionForm, setNewQuestionForm] = useState(createEmptyQuestionForm);
  const [myQuestions, setMyQuestions] = useState<StudentCourseQuestion[]>([]);

  const [expandedDiscussions, setExpandedDiscussions] = useState<number[]>([]);
  const [replyingToDiscussion, setReplyingToDiscussion] = useState<number | null>(null);
  const [discussionReplyContent, setDiscussionReplyContent] = useState('');
  const [showNewDiscussionModal, setShowNewDiscussionModal] = useState(false);
  const [newDiscussionForm, setNewDiscussionForm] = useState(createEmptyDiscussionForm);
  const [discussions, setDiscussions] = useState<CourseDiscussion[]>([]);

  const [expandedFAQs, setExpandedFAQs] = useState<number[]>([]);
  const [faqs, setFaqs] = useState<CourseFaq[]>([]);

  const [showAIToTeacherModal, setShowAIToTeacherModal] = useState(false);
  const [aiToTeacherForm, setAiToTeacherForm] = useState(createEmptyAiToTeacherForm);

  const questionAttachmentRef = useRef<HTMLInputElement>(null);

  const [examCountdown, setExamCountdown] = useState<number | null>(null);
  const examTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [homeworks, setHomeworks] = useState<StudentCourseTask[]>([]);

  const [mistakes, setMistakes] = useState<LearningMistake[]>([]);

  // 新增：学习闪卡相关状态
  const [showCreateDeckModal, setShowCreateDeckModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showStudyModal, setShowStudyModal] = useState(false);
  const [currentDeck, setCurrentDeck] = useState<FlashcardDeck | null>(null);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isCardFlipped, setIsCardFlipped] = useState(false);
  const [newDeckForm, setNewDeckForm] = useState(createEmptyDeckForm);
  const [decks, setDecks] = useState<FlashcardDeck[]>([]);
  // 处理URL参数，自动跳转到对应模块
  useEffect(() => {
    const section = searchParams.get('section');
    const taskId = searchParams.get('taskId');
    const taskType = searchParams.get('taskType');
    const chapterId = searchParams.get('chapterId');

    if (section) {
      setActiveSection(section);
      
      // 如果是任务中心，高亮显示对应的任务
      if (section === 'tasks' && taskId) {
        setHighlightedTaskId(taskId);
        // 延迟滚动到对应任务
        setTimeout(() => {
          const element = document.getElementById(`task-${taskId}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 300);
      }

      // 如果是课程资料，高亮显示对应的章节
      if (section === 'materials' && chapterId) {
        setHighlightedChapterId(chapterId);
        // 延迟滚动到对应章节
        setTimeout(() => {
          const element = document.getElementById(`chapter-${chapterId}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 300);
      }
    }
  }, [searchParams]);

  // 新增：预览文件
  const handlePreviewFile = async (file: StudentCourseMaterial) => {
    setCurrentFile(file);
    setCurrentFilePreview(null);
    setFilePreviewError('');
    setIsFilePreviewLoading(true);
    setShowPreviewModal(true);

    try {
      const preview = await courseService.getStudentCourseMaterialPreview(courseId, file.id);
      setCurrentFilePreview(preview);
    } catch (error) {
      const message = error instanceof Error ? error.message : '资料预览加载失败';
      setFilePreviewError(message);
    } finally {
      setIsFilePreviewLoading(false);
    }
  };

  // 新增：下载文件
  const handleDownloadFile = async (file: StudentCourseMaterial) => {
    try {
      const download = await courseService.downloadStudentCourseFile(courseId, file.id);
      await downloadCourseFileFromUrl(download.downloadUrl, download.fileName);
    } catch (error) {
      const message = error instanceof Error ? error.message : '资料下载失败';
      alert(message);
    }
  };

  // 新增：AI解析文件
  const handleAIAnalysis = async (file: StudentCourseMaterial) => {
    setCurrentFile(file);
    setCurrentFileAnalysis(null);
    setFileAnalysisError('');
    setIsFileAnalysisLoading(true);
    setShowAIAnalysisModal(true);

    try {
      const analysis = await courseService.getStudentCourseMaterialAnalysis(courseId, file.id);
      setCurrentFileAnalysis(analysis);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'AI解析加载失败';
      setFileAnalysisError(message);
    } finally {
      setIsFileAnalysisLoading(false);
    }
  };

  // 新增：打开知识图谱
  const handleOpenKnowledgeGraph = async () => {
    setShowKnowledgeGraphModal(true);
    try {
      const data = await courseService.getKnowledgeGraph(courseId, 'student');
      const normalized = normalizeKnowledgeGraph(data);
      const rootIds = getKnowledgeGraphRootIds(normalized);
      setGraphNodes(normalized.nodes);
      setGraphEdges(normalized.edges);
      setGraphRootIds(rootIds);
    } catch {
      // Keep the last successfully loaded graph visible.
    }
  };

  // 新增：全文搜索
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError('');
    try {
      const results = await courseService.searchStudentCourseContent(courseId, searchQuery.trim());
      setSearchResults(results);
      if (results.length === 0) {
        setSearchError('未检索到匹配片段。若资料刚上传，请等待解析和索引完成后再试。');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '搜索失败';
      setSearchError(message);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const hasIndexingCourseMaterials = courseMaterials.some((file) =>
    isMaterialIndexingStatus(file.status || file.kbStatus),
  );

  useEffect(() => {
    let mounted = true;

    courseService
      .getKnowledgeGraph(courseId, 'student')
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
    if (!hasIndexingCourseMaterials) {
      return;
    }

    let mounted = true;
    const intervalId = window.setInterval(async () => {
      try {
        const materials = await courseService.getStudentCourseMaterials(courseId);
        if (!mounted) return;
        setCourseMaterials(materials.files);

        const stillIndexing = materials.files.some((file) =>
          isMaterialIndexingStatus(file.status || file.kbStatus),
        );
        if (!stillIndexing) {
          window.clearInterval(intervalId);
          const graph = await courseService.getKnowledgeGraph(courseId, 'student');
          if (!mounted) return;
          const normalized = normalizeKnowledgeGraph(graph);
          const rootIds = getKnowledgeGraphRootIds(normalized);
          setGraphNodes(normalized.nodes);
          setGraphEdges(normalized.edges);
          setGraphRootIds(rootIds);
        }
      } catch {
        // Keep current materials visible and try again on the next tick.
      }
    }, 8000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [hasIndexingCourseMaterials, courseId]);

  useEffect(() => {
    let mounted = true;

    courseService
      .getStudentCourseMaterials(courseId)
      .then((data) => {
        if (mounted) setCourseMaterials(data.files);
      })
      .catch(() => {
        if (mounted) setCourseMaterials([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    let mounted = true;

    Promise.all([
      courseService.getStudentCourseHome(courseId),
      courseService.getStudentCourseTasks(courseId),
      courseService.getStudentCourseQuestions(courseId),
      courseService.getCourseDiscussions('student', courseId),
      courseService.getCourseFaqs(courseId),
    ])
      .then(([homeData, tasksData, questionsData, discussionsData, faqsData]) => {
        if (!mounted) return;
        setStudentHome(homeData);
        setHomeworks(tasksData.tasks);
        setMyQuestions(questionsData.questions);
        setDiscussions(discussionsData.discussions);
        setFaqs(faqsData.faqs);
      })
      .catch(() => {
        if (!mounted) return;
        setStudentHome(EMPTY_STUDENT_HOME);
        setHomeworks([]);
        setMyQuestions([]);
        setDiscussions([]);
        setFaqs([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    let mounted = true;

    Promise.all([
      learningService.getMistakes(courseId),
      learningService.getFlashcardDecks(courseId),
    ])
      .then(([mistakesData, decksData]) => {
        if (!mounted) return;
        setMistakes(mistakesData.mistakes);
        setDecks(decksData.decks);
      })
      .catch(() => {
        if (!mounted) return;
        setMistakes([]);
        setDecks([]);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  // 新增：获取过滤后的任务列表
  const getFilteredHomeworks = () => {
    if (taskFilter === 'all') return homeworks;
    if (taskFilter === 'pending') return homeworks.filter(hw => hw.status === 'pending');
    if (taskFilter === 'submitted') return homeworks.filter(hw => hw.status === 'submitted');
    if (taskFilter === 'graded') return homeworks.filter(hw => hw.status === 'graded');
    if (taskFilter === 'overdue') {
      const now = Date.now();
      return homeworks.filter(hw => {
        const deadlineTime = new Date(hw.deadline).getTime();
        return hw.status === 'pending' && Number.isFinite(deadlineTime) && deadlineTime < now;
      });
    }
    return homeworks;
  };

  // 新增：开始作业
  const handleStartHomework = (homework: any) => {
    setCurrentHomework(homework);
    setHomeworkAnswers({});
    setShowHomeworkModal(true);

    // 如果是考试且有答题时长，启动倒计时
    if (homework.isExam && homework.duration) {
      const totalSeconds = homework.duration * 60;
      setExamCountdown(totalSeconds);
      if (examTimerRef.current) clearInterval(examTimerRef.current);
      examTimerRef.current = setInterval(() => {
        setExamCountdown(prev => {
          if (prev === null || prev <= 1) {
            if (examTimerRef.current) clearInterval(examTimerRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      setExamCountdown(null);
    }
  };

  // 新增：提交作业
  const handleSubmitHomework = async () => {
    if (!currentHomework || isSubmittingHomework) return;

    const unanswered = currentHomework.questions.some((question: { id: number }) => {
      const answer = homeworkAnswers[String(question.id)];
      return !answer || !answer.trim();
    });
    if (unanswered) {
      alert('请完成所有题目后再提交');
      return;
    }

    setIsSubmittingHomework(true);
    try {
      await courseService.submitHomework(courseId, currentHomework.id, {
        answers: homeworkAnswers,
        taskType: currentHomework.isExam ? 'exam' : 'homework',
      });
      const tasksData = await courseService.getStudentCourseTasks(courseId);
      setHomeworks(tasksData.tasks);

      if (examTimerRef.current) clearInterval(examTimerRef.current);
      setExamCountdown(null);

      alert(currentHomework.isExam ? '考试答卷已提交！等待成绩发布。' : '作业提交成功！等待教师批改。');
      setShowHomeworkModal(false);
      setCurrentHomework(null);
      setHomeworkAnswers({});
    } catch (error) {
      const message = error instanceof Error ? error.message : '提交失败，请稍后重试';
      alert(`提交失败：${message}`);
    } finally {
      setIsSubmittingHomework(false);
    }
  };

  // 新增：查看批改
  const handleViewGrading = (homework: any) => {
    setCurrentHomework(homework);
    setShowGradingModal(true);
  };

  // 新增：获取过滤后的错题列表
  const getFilteredMistakes = () => {
    if (mistakeFilter === 'all') return mistakes;
    if (mistakeFilter === 'unmastered') return mistakes.filter(m => !m.mastered);
    if (mistakeFilter === 'mastered') return mistakes.filter(m => m.mastered);
    return mistakes;
  };

  const isCardDue = (card: Flashcard) => {
    if (card.due) return true;
    if (!card.nextReviewAt) return false;
    return new Date(card.nextReviewAt).getTime() <= Date.now();
  };

  const isDeckDue = (deck: FlashcardDeck) => {
    if ((deck.dueCount || 0) > 0) return true;
    if (deck.nextReview === '今天') return true;
    return deck.cardList.some(isCardDue);
  };

  // 新增：查看错题详情
  const handleViewMistake = (mistake: LearningMistake) => {
    setCurrentMistake(mistake);
    setCurrentMistakePractice(null);
    setShowMistakeDetailModal(true);
  };

  // 新增：重新练习错题
  const handlePracticeMistake = async (mistake: LearningMistake) => {
    const practice = await learningService.practiceMistake(courseId, mistake.id);
    setCurrentMistakePractice(practice);
    setCurrentMistake(practice.mistake);
    setMistakes(prev => prev.map(item => 
      item.id === mistake.id ? { ...practice.mistake } : item
    ));
    setShowMistakeDetailModal(true);
  };

  // 新增：标记错题为已掌握
  const handleMarkMastered = async (mistakeId: string | number) => {
    await learningService.markMistakeMastered(courseId, mistakeId);
    setMistakes(prev => prev.map(m => 
      m.id === mistakeId ? { ...m, mastered: true, lastPracticeTime: new Date().toISOString().split('T')[0] } : m
    ));
  };

  // 新增：添加错题
  const handleAddMistake = async () => {
    if (!newMistakeForm.question.trim() || !newMistakeForm.chapter.trim()) {
      alert('请至少填写题目和章节');
      return;
    }

    const newMistake = await learningService.createMistake(courseId, {
      question: newMistakeForm.question,
      chapter: newMistakeForm.chapter,
      myAnswer: newMistakeForm.myAnswer,
      correctAnswer: newMistakeForm.correctAnswer,
      analysis: newMistakeForm.analysis,
    });

    setMistakes([newMistake, ...mistakes]);

    alert('错题添加成功！');
    setShowAddMistakeModal(false);
    setNewMistakeForm(createEmptyMistakeForm());
  };

  // 新增：切换问题展开状态
  const toggleQuestion = (questionId: number) => {
    setExpandedQuestions(prev => 
      prev.includes(questionId) 
        ? prev.filter(id => id !== questionId)
        : [...prev, questionId]
    );
  };

  // 新增：开始回复问题
  const startReplyQuestion = (questionId: number) => {
    setReplyingToQuestion(questionId);
    setQuestionReplyContent('');
  };

  // 新增：取消回复问题
  const cancelReplyQuestion = () => {
    setReplyingToQuestion(null);
    setQuestionReplyContent('');
  };

  // 新增：提交问题回复
  const submitQuestionReply = async (questionId: number) => {
    if (!questionReplyContent.trim()) return;

    await courseService.replyStudentQuestion(courseId, questionId, {
      content: questionReplyContent,
    });
    const questionsData = await courseService.getStudentCourseQuestions(courseId);
    setMyQuestions(questionsData.questions);

    setReplyingToQuestion(null);
    setQuestionReplyContent('');
  };

  // 新增：添加新提问
  const handleAddQuestion = async () => {
    if (!newQuestionForm.title.trim() || !newQuestionForm.content.trim()) {
      alert('请填写完整的提问标题和内容');
      return;
    }

    await courseService.createStudentQuestion(courseId, {
      title: newQuestionForm.title,
      content: newQuestionForm.content,
      attachments: newQuestionForm.attachments.map((file) => file.name),
    });
    const questionsData = await courseService.getStudentCourseQuestions(courseId);
    setMyQuestions(questionsData.questions);

    alert('提问提交成功！等待教师回复。');
    setShowAddQuestionModal(false);
    setNewQuestionForm(createEmptyQuestionForm());
  };

  // 新增：处理提问附件上传
  const handleQuestionAttachmentUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    
    const newFiles = Array.from(files);
    setNewQuestionForm({ ...newQuestionForm, attachments: [...newQuestionForm.attachments, ...newFiles] });
  };

  // 新增：删除提问附件
  const removeQuestionAttachment = (index: number) => {
    setNewQuestionForm({
      ...newQuestionForm,
      attachments: newQuestionForm.attachments.filter((_, i) => i !== index)
    });
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

    await courseService.replyDiscussion('student', courseId, discussionId, {
      content: discussionReplyContent,
    });
    const discussionsData = await courseService.getCourseDiscussions('student', courseId);
    setDiscussions(discussionsData.discussions);

    setReplyingToDiscussion(null);
    setDiscussionReplyContent('');
  };

  // 新增：点赞讨论
  const toggleLikeDiscussion = async (discussionId: number) => {
    await courseService.toggleDiscussionLike('student', courseId, discussionId);
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

  // 新增：发布新讨论
  const handlePublishDiscussion = async () => {
    if (!newDiscussionForm.title.trim() || !newDiscussionForm.content.trim()) {
      alert('请填写完整的讨论标题和内容');
      return;
    }

    await courseService.createDiscussion('student', courseId, {
      title: newDiscussionForm.title,
      content: newDiscussionForm.content,
    });
    const discussionsData = await courseService.getCourseDiscussions('student', courseId);
    setDiscussions(discussionsData.discussions);

    alert('讨论发布成功！');
    setShowNewDiscussionModal(false);
    setNewDiscussionForm(createEmptyDiscussionForm());
  };

  // 新增：切换FAQ展开状态
  const toggleFAQ = (faqId: number) => {
    setExpandedFAQs(prev => 
      prev.includes(faqId) 
        ? prev.filter(id => id !== faqId)
        : [...prev, faqId]
    );
  };

  // 新增：申请AI转人工
  const handleAIToTeacherRequest = async () => {
    if (!aiToTeacherForm.title.trim() || !aiToTeacherForm.content.trim() || !aiToTeacherForm.reason.trim()) {
      alert('请填写完整的申请信息');
      return;
    }

    await courseService.requestTeacherHelp(courseId, {
      title: aiToTeacherForm.title,
      content: aiToTeacherForm.content,
      aiAnswer: aiToTeacherForm.aiAnswer,
      reason: aiToTeacherForm.reason,
    });

    alert('申请已提交！教师将尽快为您解答。');
    setShowAIToTeacherModal(false);
    setAiToTeacherForm(createEmptyAiToTeacherForm());
  };

  // 新增：开始今日复习
  const handleStartTodayReview = () => {
    const todayDecks = decks.filter(isDeckDue);
    if (todayDecks.length === 0) {
      alert('今天没有需要复习的卡片！');
      return;
    }
    
    const deck = todayDecks[0];
    const dueCards = deck.cardList.filter(card => isCardDue(card));
    setCurrentDeck({
      ...deck,
      cardList: dueCards.length > 0 ? dueCards : deck.cardList,
    });
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
    setShowReviewModal(true);
  };

  // 新增：开始学习卡组
  const handleStartStudy = (deck: FlashcardDeck) => {
    setCurrentDeck(deck);
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
    setShowStudyModal(true);
    void learningService.recordLearningEvent(courseId, {
      activity_type: 'flashcard_study_start',
      ref_id: String(deck.id),
    }).catch(() => undefined);
  };

  // 新增：翻转卡片
  const handleFlipCard = () => {
    setIsCardFlipped(!isCardFlipped);
  };

  // 新增：回答卡片（SRS算法）
  const handleAnswerCard = async (difficulty: 'forget' | 'hard' | 'good' | 'easy') => {
    if (!currentDeck) return;

    const currentCard = currentDeck.cardList[currentCardIndex];
    await learningService.submitFlashcardReview(courseId, {
      deckId: currentDeck.id,
      cardIndex: currentCardIndex,
      cardId: currentCard.id,
      difficulty,
    });

    // 移动到下一张卡片
    if (currentCardIndex < currentDeck.cardList.length - 1) {
      setCurrentCardIndex(currentCardIndex + 1);
      setIsCardFlipped(false);
    } else {
      // 完成所有卡片
      alert('恭喜！您已完成本次复习。');
      setShowReviewModal(false);
      setShowStudyModal(false);
      setCurrentDeck(null);
      setCurrentCardIndex(0);
      learningService.getFlashcardDecks(courseId).then((data) => setDecks(data.decks)).catch(() => undefined);
    }
  };

  // 新增：创建卡组
  const handleCreateDeck = async () => {
    if (!newDeckForm.name.trim()) {
      alert('请输入卡组名称');
      return;
    }

    const validCards = newDeckForm.cards.filter(c => c.front.trim() && c.back.trim());
    if (validCards.length === 0) {
      alert('请至少添加一张有效的卡片');
      return;
    }

    const newDeck = await learningService.createFlashcardDeck(courseId, {
      name: newDeckForm.name,
      cards: validCards,
    });

    setDecks([newDeck, ...decks]);

    alert('卡组创建成功！');
    setShowCreateDeckModal(false);
    setNewDeckForm(createEmptyDeckForm());
  };

  // 新增：添加卡片到表单
  const handleAddCardToForm = () => {
    setNewDeckForm({
      ...newDeckForm,
      cards: [...newDeckForm.cards, { front: '', back: '' }]
    });
  };

  // 新增：删除表单中的卡片
  const handleRemoveCardFromForm = (index: number) => {
    if (newDeckForm.cards.length === 1) {
      alert('至少需要保留一张卡片');
      return;
    }
    setNewDeckForm({
      ...newDeckForm,
      cards: newDeckForm.cards.filter((_, i) => i !== index)
    });
  };

  // 新增：更新表单中的卡片
  const handleUpdateCardInForm = (index: number, field: 'front' | 'back', value: string) => {
    const updatedCards = [...newDeckForm.cards];
    updatedCards[index][field] = value;
    setNewDeckForm({ ...newDeckForm, cards: updatedCards });
  };

  const displayName = studentHome.welcome.studentName || user?.displayName || user?.name || '学生';
  const avatarInitial = getNameInitial(displayName, '学');


  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部主导航栏 */}
      <nav className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link to="/student-dashboard" className="flex items-center gap-2">
                <img src="https://public.readdy.ai/ai/img_res/2625f127-2f4f-41ee-82d8-6c2fa4dee4ac.png" alt="珞樱学堂" className="h-9 w-9" />
                <span className="text-lg font-semibold text-gray-900">珞樱学堂</span>
              </Link>
              <div className="h-6 w-px bg-gray-300"></div>
              <div>
                <div className="text-sm font-semibold text-gray-900">{course.name}</div>
                  <div className="text-xs text-gray-500">
                    {course.teacher} · {course.code}
                    {bootstrap && ` · 进度 ${bootstrap.completionRate}% · 未读 ${bootstrap.unreadCount}`}
                  </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">{avatarInitial}</div>
            </div>
          </div>
        </div>
      </nav>

      {/* 左侧二级导航栏 */}
      <aside className="fixed left-0 top-16 bottom-0 w-56 bg-white border-r border-gray-200 z-40">
        <div className="p-4 space-y-1">
          <button onClick={() => setActiveSection('home')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'home' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-home-4-line text-base"></i>
            <span>班级首页</span>
          </button>
          <button onClick={() => setActiveSection('materials')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'materials' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-folder-open-line text-base"></i>
            <span>课程资料</span>
          </button>
          <button onClick={() => setActiveSection('tasks')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'tasks' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-task-line text-base"></i>
            <span>任务中心</span>
          </button>
          <button onClick={() => setActiveSection('interaction')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'interaction' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-chat-3-line text-base"></i>
            <span>互动空间</span>
          </button>
          <button onClick={() => setActiveSection('ai')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'ai' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-robot-line text-base"></i>
            <span>AI助教</span>
          </button>
          <button onClick={() => setActiveSection('flashcards')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'flashcards' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-stack-line text-base"></i>
            <span>学习闪卡</span>
          </button>
          <button onClick={() => setActiveSection('mylearning')} className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors cursor-pointer ${activeSection === 'mylearning' ? 'bg-teal-50 text-teal-600' : 'text-gray-700 hover:bg-gray-50'}`}>
            <i className="ri-bar-chart-box-line text-base"></i>
            <span>我的学习</span>
          </button>
        </div>
      </aside>

      {/* 右侧内容区 */}
      <main className="ml-56 pt-16 p-6">
        {courseError && (
          <div className="mx-auto mb-4 max-w-6xl rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-700">
            {courseError}
          </div>
        )}
        {activeSection === 'home' && (
          <div className="max-w-6xl mx-auto space-y-5">
            {/* 顶部 Banner：个人欢迎卡 */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-teal-600 via-teal-500 to-cyan-500 p-6 text-white">
              <div className="absolute right-0 top-0 w-72 h-full opacity-10">
                <svg viewBox="0 0 300 200" className="w-full h-full" fill="none">
                  <circle cx="250" cy="50" r="120" fill="white"/>
                  <circle cx="80" cy="180" r="80" fill="white"/>
                </svg>
              </div>
              <div className="relative flex items-center justify-between">
                <div>
                  <div className="text-xs font-medium opacity-80 mb-1">{course.name} {course.code} · {course.teacher}</div>
                  <h1 className="text-2xl font-bold mb-2">你好，{studentHome.welcome.studentName} 👋</h1>
                  <p className="text-sm opacity-90">本周已学习 <strong>{studentHome.welcome.weeklyStudyHours}</strong>，继续保持，距目标还差 <strong>{studentHome.welcome.weeklyGoalRemaining}</strong></p>
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1 text-xs font-medium">
                      <i className="ri-time-line"></i> 课程进度 {studentHome.welcome.courseProgress}%
                    </div>
                    <div className="flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1 text-xs font-medium">
                      <i className="ri-fire-line"></i> 已连续打卡 {studentHome.welcome.streakDays} 天
                    </div>
                  </div>
                </div>
                <div className="flex-shrink-0 flex items-center gap-5">
                  {/* 进度环 */}
                  <div className="relative w-28 h-28">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 112 112">
                      <circle cx="56" cy="56" r="48" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="8" />
                      <circle cx="56" cy="56" r="48" fill="none" stroke="white" strokeWidth="8"
                        strokeDasharray="301.59" strokeDashoffset={301.59 * (1 - studentHome.welcome.courseProgress / 100)} strokeLinecap="round" />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="text-2xl font-bold">{studentHome.welcome.courseProgress}%</div>
                      <div className="text-xs opacity-80">总进度</div>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {[
                      { val: studentHome.welcome.homeworkCompleted, label: '作业完成', icon: 'ri-task-line' },
                      { val: studentHome.welcome.learnedChapters, label: '已学章节', icon: 'ri-book-open-line' },
                      { val: studentHome.welcome.aiQuestions, label: 'AI提问', icon: 'ri-robot-line' },
                    ].map((s, i) => (
                      <div key={i} className="flex items-center gap-2 bg-white/15 rounded-lg px-3 py-1.5">
                        <i className={`${s.icon} text-sm opacity-90`}></i>
                        <span className="text-sm font-bold">{s.val}</span>
                        <span className="text-xs opacity-75">{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 快速入口 */}
            <div className="grid grid-cols-4 gap-3">
              {studentHome.quickActions.map((item, i) => (
                <button
                  key={i}
                  onClick={() => setActiveSection(item.section)}
                  className={`bg-gradient-to-br ${item.color} rounded-xl p-4 text-left hover:scale-[1.02] transition-transform cursor-pointer border border-white`}
                >
                  <div className={`w-9 h-9 flex items-center justify-center rounded-lg bg-white mb-3`}>
                    <i className={`${item.icon} ${item.iconColor} text-lg`}></i>
                  </div>
                  <div className="text-sm font-semibold text-gray-900">{item.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{item.sub}</div>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-5">
              {/* 课程公告 */}
              <div className="col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-gray-900">课程公告</h2>
                  <span className="text-xs text-teal-600 cursor-pointer hover:text-teal-700">全部公告</span>
                </div>
                <div className="divide-y divide-gray-50">
                  {studentHome.notices.map((notice, index) => (
                    <div key={index} className="flex items-start gap-3 px-5 py-3.5 hover:bg-gray-50 cursor-pointer">
                      <div className={`flex-shrink-0 mt-0.5 w-16 text-center`}>
                        <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${
                          notice.important ? 'bg-red-100 text-red-600' :
                          notice.tag === '资料' ? 'bg-green-100 text-green-700' :
                          notice.tag === '答疑' ? 'bg-teal-100 text-teal-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>{notice.tag}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 mb-0.5">{notice.title}</div>
                        <div className="text-xs text-gray-500 leading-relaxed line-clamp-1">{notice.content}</div>
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0 mt-0.5">{notice.time}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 近期任务 & 同班动态 */}
              <div className="space-y-5">
                {/* 近期任务截止 */}
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-gray-900">近期截止</h2>
                    <button onClick={() => setActiveSection('tasks')} className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看全部</button>
                  </div>
                  <div className="p-4 space-y-3">
                    {studentHome.upcomingTasks.map((task, i) => (
                      <div key={i} className={`flex items-center gap-3 p-2.5 rounded-lg border ${task.urgent ? 'bg-red-50 border-red-100' : 'bg-gray-50 border-gray-100'}`}>
                        <div className={`w-7 h-7 flex items-center justify-center rounded-md flex-shrink-0 ${task.urgent ? 'bg-red-100' : 'bg-white'}`}>
                          <i className={`${task.icon} text-sm ${task.urgent ? 'text-red-600' : 'text-gray-500'}`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 truncate">{task.title}</div>
                          <div className={`text-xs mt-0.5 ${task.urgent ? 'text-red-500 font-medium' : 'text-gray-400'}`}>{task.deadline}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 今日更新 */}
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-100">
                    <h2 className="text-sm font-semibold text-gray-900">今日更新</h2>
                  </div>
                  <div className="p-4 space-y-3">
                    {studentHome.todayUpdates.map((item, i) => (
                      <div key={i} className="flex items-center gap-3 cursor-pointer hover:bg-gray-50 rounded-lg p-1.5 transition-colors">
                        <div className={`w-7 h-7 flex items-center justify-center rounded-md flex-shrink-0 ${item.color}`}>
                          <i className={`${item.icon} text-sm`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-900 truncate">{item.title}</div>
                        </div>
                        <span className="text-xs text-gray-400 flex-shrink-0">{item.time}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 同班学习动态 + 课程学习里程碑 */}
            <div className="grid grid-cols-3 gap-5">
              {/* 同班动态 */}
              <div className="col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-gray-900">同班学习动态</h2>
                  <span className="text-xs text-gray-400">实时更新</span>
                </div>
                <div className="p-4">
                  <div className="space-y-3">
                    {[
                      ...studentHome.classActivities,
                    ].map((activity, index) => (
                      <div key={index} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 transition-colors">
                        <div className={`w-9 h-9 rounded-full bg-gradient-to-br ${activity.avatarBg} flex items-center justify-center text-white text-sm font-semibold flex-shrink-0`}>
                          {activity.avatar}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-medium text-gray-900">{activity.name}</span>
                            <i className={`${activity.icon} ${activity.iconColor} text-xs`}></i>
                            <span className="text-sm text-gray-600">{activity.action}</span>
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">{activity.detail} · {activity.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 学习里程碑 */}
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                  <h2 className="text-sm font-semibold text-gray-900">学习里程碑</h2>
                  <p className="text-xs text-gray-400 mt-0.5">课程节点与考核安排</p>
                </div>
                <div className="p-4">
                  <div className="relative">
                    <div className="absolute left-3.5 top-0 bottom-0 w-px bg-gray-100"></div>
                    <div className="space-y-4">
                      {studentHome.milestones.map((milestone, i) => (
                        <div key={i} className="flex items-start gap-3 relative pl-1">
                          <div className={`relative z-10 w-6 h-6 flex items-center justify-center rounded-full flex-shrink-0 border-2 ${
                            milestone.done
                              ? 'bg-green-500 border-green-500'
                              : milestone.urgent
                              ? 'bg-red-500 border-red-500 animate-pulse'
                              : milestone.current
                              ? 'bg-teal-500 border-teal-500'
                              : 'bg-white border-gray-200'
                          }`}>
                            {milestone.done ? (
                              <i className="ri-check-line text-white text-xs"></i>
                            ) : milestone.urgent ? (
                              <i className="ri-alarm-warning-line text-white text-xs"></i>
                            ) : milestone.current ? (
                              <div className="w-2 h-2 rounded-full bg-white"></div>
                            ) : (
                              <div className="w-2 h-2 rounded-full bg-gray-300"></div>
                            )}
                          </div>
                          <div className="flex-1 pt-0.5">
                            <div className={`text-xs font-medium ${milestone.done ? 'text-gray-400 line-through' : milestone.urgent ? 'text-red-600' : 'text-gray-900'}`}>
                              {milestone.title}
                            </div>
                            <div className={`text-xs mt-0.5 ${milestone.done ? 'text-gray-300' : milestone.urgent ? 'text-red-400 font-medium' : 'text-gray-400'}`}>
                              {milestone.date}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 课程整体进度条 */}
                  <div className="mt-5 pt-4 border-t border-gray-100">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                      <span>课程整体进度</span>
                      <span className="font-semibold text-teal-600">{studentHome.progress.percent}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-teal-400 to-cyan-400 rounded-full transition-all duration-700" style={{ width: `${studentHome.progress.percent}%` }}></div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-gray-400 mt-1.5">
                      <span>开课 {studentHome.progress.startDate}</span>
                      <span>结课 {studentHome.progress.endDate}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeSection === 'materials' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-bold text-gray-900">课程资料</h1>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <input 
                    type="text" 
                    placeholder="全文搜索..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                  />
                  <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-base"></i>
                </div>
                <button 
                  onClick={handleOpenKnowledgeGraph}
                  className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                >
                  <i className="ri-mind-map mr-1"></i>知识图谱
                </button>
              </div>
            </div>

            {(isSearching || searchError || searchResults.length > 0) && (
              <div className="bg-white rounded-lg border border-gray-200">
                <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                  <div className="text-sm font-semibold text-gray-900">搜索结果</div>
                  {searchResults.length > 0 && (
                    <button
                      onClick={() => {
                        setSearchResults([]);
                        setSearchError('');
                      }}
                      className="text-xs text-gray-500 hover:text-gray-700 cursor-pointer"
                    >
                      清空
                    </button>
                  )}
                </div>
                <div className="p-5 space-y-3">
                  {isSearching && <div className="text-sm text-gray-500">正在检索课程资料...</div>}
                  {!isSearching && searchError && (
                    <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                      {searchError}
                    </div>
                  )}
                  {!isSearching && searchResults.map((result) => (
                    <div key={`${result.material_id}-${result.chunk_id || result.page || result.score}`} className="rounded-lg border border-gray-200 p-4">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {result.source_name || '课程资料'}
                        </div>
                        <div className="text-xs text-gray-500 whitespace-nowrap">
                          匹配度 {Math.round((result.score || 0) * 100)}%
                          {result.page ? ` · 第 ${result.page} 页` : ''}
                        </div>
                      </div>
                      <div className="text-sm text-gray-700 leading-6 whitespace-pre-line">
                        {result.snippet}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 资料列表 */}
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="divide-y divide-gray-100">
                {courseMaterials.length === 0 && (
                  <StudentCourseEmptyState
                    icon="ri-folder-open-line"
                    title="暂无课程资料"
                    description="后端返回空资料列表时会显示这里，后续教师上传资料后将自动展示。"
                  />
                )}
                {courseMaterials.map((file) => (
                  <div 
                    key={file.id} 
                    id={`chapter-${file.id}`}
                    className={`flex items-center gap-4 px-5 py-4 hover:bg-gray-50 cursor-pointer transition-all ${
                      highlightedChapterId === file.id ? 'bg-teal-50 border-l-4 border-teal-500' : ''
                    }`}
                  >
                    <div className={`w-10 h-10 flex items-center justify-center rounded-lg flex-shrink-0 ${
                      file.type === 'pdf' ? 'bg-red-50' :
                      file.type === 'ppt' ? 'bg-orange-50' :
                      file.type === 'video' ? 'bg-purple-50' :
                      'bg-blue-50'
                    }`}>
                      <i className={`text-lg ${
                        file.type === 'pdf' ? 'ri-file-pdf-line text-red-600' :
                        file.type === 'ppt' ? 'ri-file-ppt-line text-orange-600' :
                        file.type === 'video' ? 'ri-video-line text-purple-600' :
                        'ri-file-code-line text-blue-600'
                      }`}></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="truncate text-sm font-medium text-gray-900">{file.name}</div>
                        <span className={`shrink-0 px-2 py-0.5 text-xs font-medium rounded-full ${getMaterialStatusMeta(file.status || file.kbStatus).className}`}>
                          {getMaterialStatusMeta(file.status || file.kbStatus).label}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {file.size} · {file.date} · {file.views}次观看
                        {file.kbError ? <span className="ml-2 text-red-500">解析异常</span> : null}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {file.type === 'video' && (
                        <select 
                          value={videoSpeed}
                          onChange={(e) => setVideoSpeed(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="px-2 py-1 text-xs border border-gray-300 rounded cursor-pointer"
                        >
                          <option value="1.0">1.0x</option>
                          <option value="1.25">1.25x</option>
                          <option value="1.5">1.5x</option>
                          <option value="2.0">2.0x</option>
                        </select>
                      )}
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePreviewFile(file);
                        }}
                        className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-eye-line mr-1"></i>预览
                      </button>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadFile(file);
                        }}
                        className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 rounded-md hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-download-line mr-1"></i>下载
                      </button>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAIAnalysis(file);
                        }}
                        className="px-3 py-1.5 text-xs font-medium text-purple-600 bg-purple-50 rounded-md hover:bg-purple-100 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-ai-generate mr-1"></i>AI解析
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeSection === 'tasks' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <h1 className="text-xl font-bold text-gray-900">任务中心</h1>

            {/* 任务统计 */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">待完成作业</div>
                    <div className="text-2xl font-bold text-orange-600">
                      {homeworks.filter(hw => hw.status === 'pending').length}
                    </div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-file-list-3-line text-orange-600 text-lg"></i>
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">已完成作业</div>
                    <div className="text-2xl font-bold text-green-600">
                      {homeworks.filter(hw => hw.status === 'graded').length}
                    </div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-checkbox-circle-line text-green-600 text-lg"></i>
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">未读通知</div>
                    <div className="text-2xl font-bold text-blue-600">5</div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-notification-3-line text-blue-600 text-lg"></i>
                  </div>
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-600 mb-1">错题数量</div>
                    <div className="text-2xl font-bold text-red-600">{mistakes.length}</div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-red-50">
                    <i className="ri-error-warning-line text-red-600 text-lg"></i>
                  </div>
                </div>
              </div>
            </div>

            {/* 作业列表 */}
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="px-5 py-3 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => setTaskFilter('all')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${
                      taskFilter === 'all' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    全部
                  </button>
                  <button 
                    onClick={() => setTaskFilter('pending')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${
                      taskFilter === 'pending' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    待完成
                  </button>
                  <button 
                    onClick={() => setTaskFilter('submitted')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${
                      taskFilter === 'submitted' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    已提交
                  </button>
                  <button 
                    onClick={() => setTaskFilter('graded')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${
                      taskFilter === 'graded' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    已批改
                  </button>
                  <button 
                    onClick={() => setTaskFilter('overdue')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${
                      taskFilter === 'overdue' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    已逾期
                  </button>
                </div>
              </div>
              <div className="divide-y divide-gray-100">
                {getFilteredHomeworks().length === 0 && (
                  <StudentCourseEmptyState
                    icon="ri-task-line"
                    title="暂无匹配任务"
                    description="当前筛选下没有作业、考试或通知，后端返回空数组时页面会保持可用。"
                  />
                )}
                {getFilteredHomeworks().map((homework, index) => (
                  <div 
                    key={index} 
                    id={`task-${homework.id}`}
                    className={`flex items-center gap-4 px-5 py-4 hover:bg-gray-50 cursor-pointer transition-all ${
                      homework.urgent ? 'bg-red-50/30' : ''
                    } ${highlightedTaskId === homework.id ? 'bg-teal-50 border-l-4 border-teal-500' : ''}`}
                  >
                    <div className={`w-10 h-10 flex items-center justify-center rounded-lg flex-shrink-0 ${
                      homework.status === 'pending' ? 'bg-orange-50' :
                      homework.status === 'submitted' ? 'bg-blue-50' :
                      'bg-green-50'
                    }`}>
                      <i className={`text-lg ${
                        homework.status === 'pending' ? 'ri-file-list-3-line text-orange-600' :
                        homework.status === 'submitted' ? 'ri-time-line text-blue-600' :
                        'ri-checkbox-circle-line text-green-600'
                      }`}></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">
                        {homework.title}
                        {homework.isExam && <span className="ml-2 px-2 py-0.5 text-xs font-medium text-purple-600 bg-purple-50 rounded">考试</span>}
                      </div>
                      <div className="text-xs text-gray-500 mt-1 space-x-2">
                        {homework.isExam && (homework as any).startTime ? (
                          <span>开放时间：{(homework as any).startTime} ~ {homework.deadline}</span>
                        ) : (
                          <span>截止时间: {homework.deadline}</span>
                        )}
                        {homework.isExam && (homework as any).duration && (
                          <span className="inline-flex items-center gap-1 text-purple-600 font-medium">
                            <i className="ri-timer-line"></i>答题时长 {(homework as any).duration} 分钟
                          </span>
                        )}
                        {homework.score !== null && <span>· 得分: {homework.score}分</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {homework.status === 'pending' && (
                        <button 
                          onClick={() => handleStartHomework(homework)}
                          className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 rounded-md hover:bg-teal-700 cursor-pointer whitespace-nowrap"
                        >
                          {homework.isExam ? '开始考试' : '开始作业'}
                        </button>
                      )}
                      {homework.status === 'submitted' && (
                        <span className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-md">
                          批改中
                        </span>
                      )}
                      {homework.status === 'graded' && (
                        <button 
                          onClick={() => handleViewGrading(homework)}
                          className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 rounded-md hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                        >
                          查看批改
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 错题本 */}
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="px-5 py-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900">错题本</h2>
                  <div className="flex items-center gap-2">
                    <select
                      value={mistakeFilter}
                      onChange={(e) => setMistakeFilter(e.target.value)}
                      className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-white cursor-pointer"
                    >
                      <option value="all">全部错题</option>
                      <option value="unmastered">未掌握</option>
                      <option value="mastered">已掌握</option>
                    </select>
                    <button 
                      onClick={() => setShowAddMistakeModal(true)}
                      className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-add-line mr-1"></i>添加错题
                    </button>
                  </div>
                </div>
              </div>
              <div className="divide-y divide-gray-100">
                {getFilteredMistakes().length === 0 && (
                  <StudentCourseEmptyState
                    icon="ri-bookmark-line"
                    title="暂无错题记录"
                    description="普通账号尚未产生错题时会显示这里，后续练习或手动添加后将展示错题。"
                  />
                )}
                {getFilteredMistakes().map((mistake) => (
                  <div key={mistake.id} className="px-5 py-4 hover:bg-gray-50">
                    <div className="flex items-start gap-3">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                        mistake.mastered ? 'bg-green-50' : 'bg-red-50'
                      }`}>
                        <i className={`text-base ${
                          mistake.mastered ? 'ri-checkbox-circle-line text-green-600' : 'ri-close-circle-line text-red-600'
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 mb-2">{mistake.question}</div>
                        <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                          <span>{mistake.chapter}</span>
                          <span>错误{mistake.wrongCount}次</span>
                          <span>最后练习: {mistake.lastPracticeTime}</span>
                          {mistake.mastered && (
                            <span className="px-2 py-0.5 text-xs font-medium text-green-600 bg-green-50 rounded">已掌握</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button 
                            onClick={() => handleViewMistake(mistake)}
                            className="px-2 py-1 text-xs font-medium text-gray-600 bg-gray-50 rounded cursor-pointer whitespace-nowrap"
                          >
                            查看详情
                          </button>
                          <button 
                            onClick={() => handlePracticeMistake(mistake)}
                            className="px-2 py-1 text-xs font-medium text-teal-600 bg-teal-50 rounded cursor-pointer whitespace-nowrap"
                          >
                            重新练习
                          </button>
                          {!mistake.mastered && (
                            <button 
                              onClick={() => handleMarkMastered(mistake.id)}
                              className="px-2 py-1 text-xs font-medium text-green-600 bg-green-50 rounded cursor-pointer whitespace-nowrap"
                            >
                              标记已掌握
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeSection === 'interaction' && (
          <div className="max-w-6xl mx-auto">
            <h1 className="text-xl font-bold text-gray-900 mb-4">互动空间</h1>
            <div className="grid grid-cols-3 gap-5">
              {/* 我的提问 */}
              <div className="col-span-2 space-y-5">
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-base font-semibold text-gray-900">我的提问</h2>
                    <button 
                      onClick={() => setShowAddQuestionModal(true)}
                      className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-add-line mr-1"></i>添加提问
                    </button>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {myQuestions.length === 0 && (
                      <StudentCourseEmptyState
                        icon="ri-question-answer-line"
                        title="暂无提问"
                        description="当前课程还没有提问记录，可以点击添加提问发起答疑。"
                      />
                    )}
                    {myQuestions.map((item) => (
                      <div key={item.id} className="px-5 py-4 hover:bg-gray-50">
                        <div className="flex items-start gap-3">
                          <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                            item.status === 'answered' ? 'bg-green-50' : 'bg-orange-50'
                          }`}>
                            <i className={`text-base ${
                              item.status === 'answered' ? 'ri-checkbox-circle-line text-green-600' : 'ri-time-line text-orange-600'
                            }`}></i>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 
                                onClick={() => toggleQuestion(item.id)}
                                className="text-sm font-medium text-gray-900 cursor-pointer hover:text-teal-600"
                              >
                                {item.title}
                              </h3>
                              {item.status === 'answered' ? (
                                <span className="px-2 py-0.5 text-xs font-medium bg-green-50 text-green-600 rounded-full">已回复</span>
                              ) : (
                                <span className="px-2 py-0.5 text-xs font-medium bg-orange-50 text-orange-600 rounded-full">待回复</span>
                              )}
                            </div>

                            {/* 展开的问题内容 */}
                            {expandedQuestions.includes(item.id) && (
                              <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line mb-3">
                                  {item.content}
                                </div>
                                <div className="text-xs text-gray-500">提问时间：{item.time}</div>
                              </div>
                            )}

                            {/* 回复列表 */}
                            {expandedQuestions.includes(item.id) && item.replies.length > 0 && (
                              <div className="mt-3 space-y-2">
                                {item.replies.map((reply, idx) => (
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
                            {expandedQuestions.includes(item.id) && replyingToQuestion === item.id && (
                              <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                <textarea
                                  value={questionReplyContent}
                                  onChange={(e) => setQuestionReplyContent(e.target.value)}
                                  placeholder="输入您的回复..."
                                  rows={3}
                                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none"
                                ></textarea>
                                <div className="flex items-center justify-end gap-2 mt-2">
                                  <button
                                    onClick={cancelReplyQuestion}
                                    className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                                  >
                                    取消
                                  </button>
                                  <button
                                    onClick={() => submitQuestionReply(item.id)}
                                    disabled={!questionReplyContent.trim()}
                                    className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 rounded-md hover:bg-teal-700 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    发送回复
                                  </button>
                                </div>
                              </div>
                            )}

                            <div className="flex items-center gap-3 mt-2">
                              <span className="text-xs text-gray-400">{item.time}</span>
                              {expandedQuestions.includes(item.id) && replyingToQuestion !== item.id && (
                                <button 
                                  onClick={() => startReplyQuestion(item.id)}
                                  className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap"
                                >
                                  回复
                                </button>
                              )}
                              <button
                                onClick={() => toggleQuestion(item.id)}
                                className="text-xs text-gray-500 hover:text-gray-700 cursor-pointer whitespace-nowrap"
                              >
                                {expandedQuestions.includes(item.id) ? '收起' : '展开详情'}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 班级讨论 */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-base font-semibold text-gray-900">班级讨论</h2>
                    <button 
                      onClick={() => setShowNewDiscussionModal(true)}
                      className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-add-line mr-1"></i>发起讨论
                    </button>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {discussions.length === 0 && (
                      <StudentCourseEmptyState
                        icon="ri-discuss-line"
                        title="暂无讨论"
                        description="当前班级还没有讨论帖，发起讨论后会显示在这里。"
                      />
                    )}
                    {discussions.map((discussion) => (
                      <div key={discussion.id} className="px-5 py-4 hover:bg-gray-50">
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-medium flex-shrink-0">
                            {discussion.student[0]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-gray-900">{discussion.student}</span>
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
                                  <div key={idx} className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                                    <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                                      {reply.author[0]}
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
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 右侧栏 */}
              <div className="space-y-5">
                {/* 集中答疑 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">集中答疑</h2>
                  <div className="space-y-3">
                    {faqs.length === 0 && (
                      <StudentCourseEmptyState
                        icon="ri-chat-smile-line"
                        title="暂无集中答疑"
                        description="教师发布集中答疑后会展示在这里。"
                      />
                    )}
                    {faqs.map((faq) => (
                      <div key={faq.id}>
                        <div 
                          onClick={() => toggleFAQ(faq.id)}
                          className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 cursor-pointer"
                        >
                          <div className="text-sm font-medium text-gray-900 mb-2">{faq.title}</div>
                          <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>{faq.date}</span>
                            <span>{faq.views}次查看</span>
                          </div>
                        </div>

                        {/* 展开的FAQ内容 */}
                        {expandedFAQs.includes(faq.id) && (
                          <div className="mt-2 p-4 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-line mb-3">
                              {faq.content}
                            </div>
                            {faq.attachments.length > 0 && (
                              <div>
                                <div className="text-xs text-gray-500 mb-2">附件：</div>
                                <div className="space-y-1">
                                  {faq.attachments.map((attachment, idx) => (
                                    <div key={idx} className="flex items-center gap-2 p-2 bg-white rounded border border-gray-200">
                                      <i className="ri-file-pdf-line text-red-500 text-base"></i>
                                      <span className="flex-1 text-xs text-gray-700">{attachment}</span>
                                      <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">
                                        <i className="ri-download-line mr-1"></i>下载
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI转人工 */}
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg p-5 border border-purple-100">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-100">
                      <i className="ri-customer-service-2-line text-purple-600 text-base"></i>
                    </div>
                    <h2 className="text-base font-semibold text-gray-900">AI转人工</h2>
                  </div>
                  <p className="text-sm text-gray-600 mb-4">AI回答不满意？可以申请教师介入解答</p>
                  <button 
                    onClick={() => setShowAIToTeacherModal(true)}
                    className="w-full px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 cursor-pointer whitespace-nowrap"
                  >
                    申请教师解答
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeSection === 'ai' && (
          <div className="h-[calc(100vh-5.5rem)] min-h-[680px]">
            <AIAssistant />
          </div>
        )}

        {activeSection === 'flashcards' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-bold text-gray-900">学习闪卡</h1>
              <button 
                onClick={() => setShowCreateDeckModal(true)}
                className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line mr-1"></i>创建卡组
              </button>
            </div>

            {/* 今日复习 */}
            <div className="bg-gradient-to-r from-teal-500 to-blue-500 rounded-xl p-6 text-white">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold mb-1">今日复习</h2>
                  <p className="text-sm opacity-90">基于间隔重复算法为您安排</p>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold">
                    {decks.reduce((sum, deck) => sum + (deck.dueCount ?? deck.cardList.filter(isCardDue).length), 0)}
                  </div>
                  <div className="text-sm opacity-90">张卡片待复习</div>
                </div>
              </div>
              <button 
                onClick={handleStartTodayReview}
                className="w-full px-4 py-3 bg-white text-teal-600 text-sm font-medium rounded-lg hover:bg-gray-50 cursor-pointer whitespace-nowrap"
              >
                开始复习
              </button>
            </div>

            {/* 卡组列表 */}
            <div className="grid grid-cols-3 gap-5">
              {decks.length === 0 && (
                <div className="col-span-3">
                  <StudentCourseEmptyState
                    icon="ri-flashlight-line"
                    title="暂无闪卡卡组"
                    description="创建卡组或后端返回推荐卡组后，会显示在这里。"
                  />
                </div>
              )}
              {decks.map((deck) => (
                <div key={deck.id} className="bg-white rounded-lg p-5 border border-gray-200 hover:shadow-lg transition-shadow">
                  <h3 className="text-base font-semibold text-gray-900 mb-4">{deck.name}</h3>
                  <div className="space-y-3 mb-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">总卡片数</span>
                      <span className="font-medium text-gray-900">{deck.cards}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">已掌握</span>
                      <span className="font-medium text-green-600">{deck.mastered}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">学习中</span>
                      <span className="font-medium text-blue-600">{deck.learning}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">新卡片</span>
                      <span className="font-medium text-orange-600">{deck.new}</span>
                    </div>
                  </div>
                  <div className="pt-3 border-t border-gray-200">
                    <div className="text-xs text-gray-500 mb-2">下次复习: {deck.nextReview}</div>
                    <button 
                      onClick={() => handleStartStudy(deck)}
                      className="w-full px-3 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                    >
                      开始学习
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* 学习模式说明 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <h2 className="text-base font-semibold text-gray-900 mb-4">间隔重复算法(SRS)</h2>
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center p-4 rounded-lg bg-red-50">
                  <div className="w-12 h-12 flex items-center justify-center rounded-full bg-red-100 mx-auto mb-2">
                    <i className="ri-close-line text-red-600 text-xl"></i>
                  </div>
                  <div className="text-sm font-medium text-gray-900 mb-1">忘记</div>
                  <div className="text-xs text-gray-600">1天后再次复习</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-orange-50">
                  <div className="w-12 h-12 flex items-center justify-center rounded-full bg-orange-100 mx-auto mb-2">
                    <i className="ri-question-line text-orange-600 text-xl"></i>
                  </div>
                  <div className="text-sm font-medium text-gray-900 mb-1">模糊</div>
                  <div className="text-xs text-gray-600">2天后再次复习</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-blue-50">
                  <div className="w-12 h-12 flex items-center justify-center rounded-full bg-blue-100 mx-auto mb-2">
                    <i className="ri-check-line text-blue-600 text-xl"></i>
                  </div>
                  <div className="text-sm font-medium text-gray-900 mb-1">记得</div>
                  <div className="text-xs text-gray-600">6天后再次复习</div>
                </div>
                <div className="text-center p-4 rounded-lg bg-green-50">
                  <div className="w-12 h-12 flex items-center justify-center rounded-full bg-green-100 mx-auto mb-2">
                    <i className="ri-thumb-up-line text-green-600 text-xl"></i>
                  </div>
                  <div className="text-sm font-medium text-gray-900 mb-1">简单</div>
                  <div className="text-xs text-gray-600">15天后再次复习</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeSection === 'mylearning' && <MyLearning courseId={courseId} />}

        {/* 预览文件弹窗 */}
        {showPreviewModal && currentFile && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">预览 - {currentFile.name}</h2>
                  <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                    <span className={`px-2 py-0.5 font-medium rounded-full ${getMaterialStatusMeta(currentFile.status || currentFile.kbStatus).className}`}>
                      {getMaterialStatusMeta(currentFile.status || currentFile.kbStatus).label}
                    </span>
                    {currentFile.kbError ? <span className="text-red-500">{currentFile.kbError}</span> : null}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {currentFile.type === 'video' && (
                    <select 
                      value={videoSpeed}
                      onChange={(e) => setVideoSpeed(e.target.value)}
                      className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-white cursor-pointer"
                    >
                      <option value="1.0">1.0x</option>
                      <option value="1.25">1.25x</option>
                      <option value="1.5">1.5x</option>
                      <option value="2.0">2.0x</option>
                    </select>
                  )}
                  <button
                    onClick={() => {
                      setShowPreviewModal(false);
                      setCurrentFilePreview(null);
                      setFilePreviewError('');
                    }}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                {isFilePreviewLoading ? (
                  <div className="min-h-[420px] flex items-center justify-center text-sm text-gray-500">
                    正在加载预览...
                  </div>
                ) : filePreviewError ? (
                  <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                    {filePreviewError}
                  </div>
                ) : currentFilePreview?.previewType === 'video' && currentFilePreview.previewUrl ? (
                  <video controls className="w-full rounded-lg bg-black">
                    <source src={currentFilePreview.previewUrl} />
                  </video>
                ) : currentFilePreview?.previewUrl ? (
                  <iframe
                    title={`student-preview-${currentFile.id}`}
                    src={currentFilePreview.previewUrl}
                    className="h-[520px] w-full rounded-lg border border-gray-200 bg-white"
                  />
                ) : currentFilePreview?.textContent?.trim() ? (
                  <div className="rounded-lg border border-gray-200 bg-white">
                    <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
                      <div className="text-sm font-medium text-gray-900">资料内容</div>
                      <div className="text-xs text-gray-400">
                        {currentFilePreview.previewSource === 'original_file' ? '原始文件' : '解析文本'}
                        {currentFilePreview.textTruncated ? ' · 已截断显示' : ''}
                      </div>
                    </div>
                    <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap break-words p-4 text-sm leading-6 text-gray-700">
                      {currentFilePreview.textContent}
                    </pre>
                  </div>
                ) : currentFile.type === 'video' ? (
                  <div className="aspect-video bg-black rounded-lg flex items-center justify-center relative">
                    <div className="text-center text-white">
                      <i className="ri-play-circle-line text-6xl mb-3"></i>
                      <div className="text-sm">视频预览 - 倍速: {videoSpeed}x</div>
                    </div>
                    <div className="absolute bottom-4 left-4 right-4 bg-black/50 rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <button className="w-8 h-8 flex items-center justify-center text-white hover:text-teal-400 cursor-pointer">
                          <i className="ri-play-fill text-xl"></i>
                        </button>
                        <div className="flex-1 h-1 bg-gray-600 rounded-full">
                          <div className="h-full bg-teal-500 rounded-full" style={{ width: '35%' }}></div>
                        </div>
                        <span className="text-xs text-white">05:23 / 15:18</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="border border-gray-200 rounded-lg p-8 bg-gray-50 min-h-[600px] flex items-center justify-center">
                    <div className="text-center text-gray-400">
                      <i className={`${currentFile.type === 'pdf' ? 'ri-file-pdf-line' : currentFile.type === 'ppt' ? 'ri-file-ppt-line' : 'ri-file-code-line'} text-6xl mb-3`}></i>
                      <div className="text-sm">暂无可预览文本</div>
                      <div className="text-xs text-gray-400 mt-2">{currentFilePreview?.note || '可先下载原文件查看'}</div>
                    </div>
                  </div>
                )}
                {currentFilePreview?.note && (
                  <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-600">
                    {currentFilePreview.note}
                  </div>
                )}
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-2">
                  {currentFile.type !== 'video' && (
                    <>
                      <button className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">
                        <i className="ri-arrow-left-line mr-1"></i>上一页
                      </button>
                      <button className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">
                        下一页<i className="ri-arrow-right-line ml-1"></i>
                      </button>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDownloadFile(currentFile)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-download-line mr-1"></i>下载
                  </button>
                  <button
                    onClick={() => {
                      setShowPreviewModal(false);
                      setCurrentFilePreview(null);
                      setFilePreviewError('');
                    }}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    关闭
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* AI解析弹窗 */}
        {showAIAnalysisModal && currentFile && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">AI解析 - {currentFile.name}</h2>
                  <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                    <span className={`px-2 py-0.5 font-medium rounded-full ${getMaterialStatusMeta(currentFile.status || currentFile.kbStatus).className}`}>
                      {getMaterialStatusMeta(currentFile.status || currentFile.kbStatus).label}
                    </span>
                    {currentFile.kbError ? <span className="text-red-500">{currentFile.kbError}</span> : null}
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowAIAnalysisModal(false);
                    setCurrentFileAnalysis(null);
                    setFileAnalysisError('');
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                {isFileAnalysisLoading && (
                  <div className="mb-4 rounded-lg border border-teal-100 bg-teal-50 px-4 py-3 text-sm text-teal-700">
                    正在读取资料解析结果...
                  </div>
                )}
                {fileAnalysisError && (
                  <div className="mb-4 rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                    {fileAnalysisError}
                  </div>
                )}
                <div className="space-y-5">
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">内容摘要</div>
                    <div className="text-sm text-gray-700 leading-relaxed">
                      {currentFileAnalysis?.summary || '资料已上传，解析完成后将展示自动摘要。你也可以先下载原文件查看。'}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">核心知识点</div>
                    <div className="space-y-2">
                      {(currentFileAnalysis?.keyPoints?.length ? currentFileAnalysis.keyPoints : ['暂无关键词，等待资料解析完成']).map((point, i) => (
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
                      {(currentFileAnalysis?.difficulties?.length ? currentFileAnalysis.difficulties : [{ title: '等待解析结果', difficulty: '基础' as const }]).map((item, i) => (
                        <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">{item.title}</span>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              item.difficulty === '较难' ? 'bg-orange-100 text-orange-600' : 'bg-yellow-100 text-yellow-600'
                            }`}>{item.difficulty}</span>
                          </div>
                          <div className="text-xs text-gray-600">建议结合原文和 AI 助教问答进一步理解。</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">学习建议</div>
                    <div className="text-sm text-gray-700 leading-relaxed space-y-2">
                      <p>• 建议学习时长：{currentFileAnalysis?.recommendedStudyDuration || '等待解析结果'}</p>
                      <p>• 若预览为空，说明文本解析可能仍在进行，可先下载原文件学习。</p>
                      <p>• 解析完成后，可围绕核心知识点向 AI 助教追问。</p>
                      <p>• 后续错题和闪卡会优先结合已解析资料进行推荐。</p>
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">相关资料推荐</div>
                    <div className="space-y-2">
                      {[
                        { name: '第2章 物理层.pptx', type: 'ppt' },
                        { name: 'TCP协议详解视频.mp4', type: 'video' },
                        { name: '网络协议分析实验.pdf', type: 'pdf' }
                      ].map((file, i) => (
                        <div key={i} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg border border-gray-200 hover:border-teal-200 hover:bg-teal-50 transition-colors cursor-pointer">
                          <i className={`text-base ${
                            file.type === 'pdf' ? 'ri-file-pdf-line text-red-500' :
                            file.type === 'video' ? 'ri-video-line text-purple-500' :
                            'ri-file-ppt-line text-orange-500'
                          }`}></i>
                          <span className="flex-1 text-sm text-gray-700">{file.name}</span>
                          <i className="ri-arrow-right-line text-gray-400"></i>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end flex-shrink-0">
                <button
                  onClick={() => {
                    setShowAIAnalysisModal(false);
                    setCurrentFileAnalysis(null);
                    setFileAnalysisError('');
                  }}
                  className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 知识图谱弹窗 */}
        {showKnowledgeGraphModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="w-full max-w-6xl max-h-[90vh] overflow-hidden">
              <KnowledgeGraphViewer
                nodes={graphNodes}
                edges={graphEdges}
                rootIds={graphRootIds}
                heightClassName="h-[620px]"
                showCloseButton
                onClose={() => setShowKnowledgeGraphModal(false)}
              />
            </div>
          </div>
        )}

        {/* 开始作业弹窗 */}
        {showHomeworkModal && currentHomework && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{currentHomework.title}</h2>
                  {currentHomework.isExam && (currentHomework as any).startTime && (
                    <div className="text-xs text-gray-500 mt-0.5">
                      开放时间：{(currentHomework as any).startTime} ~ {currentHomework.deadline}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {/* 倒计时显示 */}
                  {currentHomework.isExam && examCountdown !== null && (
                    <div className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono font-bold text-sm ${
                      examCountdown <= 300 ? 'bg-red-100 text-red-600' :
                      examCountdown <= 600 ? 'bg-orange-100 text-orange-600' :
                      'bg-teal-50 text-teal-700'
                    }`}>
                      <i className={`ri-timer-line text-base ${examCountdown <= 300 ? 'animate-pulse' : ''}`}></i>
                      {(() => {
                        const h = Math.floor(examCountdown / 3600);
                        const m = Math.floor((examCountdown % 3600) / 60);
                        const s = examCountdown % 60;
                        return h > 0
                          ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
                          : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
                      })()}
                      {examCountdown === 0 && <span className="ml-1 text-xs font-normal">时间到</span>}
                    </div>
                  )}
                  <button
                    onClick={() => {
                      if (examTimerRef.current) clearInterval(examTimerRef.current);
                      setExamCountdown(null);
                      setShowHomeworkModal(false);
                      setCurrentHomework(null);
                      setHomeworkAnswers({});
                    }}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {currentHomework.questions.map((question: any, index: number) => (
                    <div key={question.id} className="p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-start gap-3 mb-3">
                        <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-teal-100 text-teal-600 text-xs font-semibold">
                          {index + 1}
                        </span>
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900 mb-2">{question.content}</div>
                          {question.type === 'text' ? (
                            <textarea
                              rows={4}
                              value={homeworkAnswers[question.id] || ''}
                              onChange={(e) => setHomeworkAnswers({ ...homeworkAnswers, [question.id]: e.target.value })}
                              placeholder="请输入您的答案..."
                              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                            ></textarea>
                          ) : (
                            <textarea
                              rows={8}
                              value={homeworkAnswers[question.id] || ''}
                              onChange={(e) => setHomeworkAnswers({ ...homeworkAnswers, [question.id]: e.target.value })}
                              placeholder="请输入您的代码..."
                              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 font-mono"
                            ></textarea>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between flex-shrink-0">
                <div className="text-sm text-gray-600">
                  已完成 {currentHomework.questions.filter((question: { id: number }) => (homeworkAnswers[String(question.id)] || '').trim()).length} / {currentHomework.questions.length} 题
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      if (examTimerRef.current) clearInterval(examTimerRef.current);
                      setExamCountdown(null);
                      setShowHomeworkModal(false);
                      setCurrentHomework(null);
                      setHomeworkAnswers({});
                    }}
                    disabled={isSubmittingHomework}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    暂存草稿
                  </button>
                  <button
                    onClick={handleSubmitHomework}
                    disabled={isSubmittingHomework}
                    className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {isSubmittingHomework ? '提交中...' : currentHomework.isExam ? '提交考试' : '提交作业'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 查看批改弹窗 */}
        {showGradingModal && currentHomework && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{currentHomework.title}</h2>
                  <div className="text-sm text-gray-600 mt-1">得分: {currentHomework.score}分</div>
                </div>
                <button
                  onClick={() => {
                    setShowGradingModal(false);
                    setCurrentHomework(null);
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {currentHomework.questions.map((question: any, index: number) => (
                    <div key={question.id} className={`p-4 border rounded-lg ${
                      question.correct ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-red-50/30'
                    }`}>
                      <div className="flex items-start gap-3 mb-3">
                        <span className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full text-xs font-semibold ${
                          question.correct ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                        }`}>
                          {index + 1}
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <div className="text-sm font-medium text-gray-900">{question.content}</div>
                            {question.correct ? (
                              <span className="px-2 py-0.5 text-xs font-medium text-green-600 bg-green-100 rounded">正确</span>
                            ) : (
                              <span className="px-2 py-0.5 text-xs font-medium text-red-600 bg-red-100 rounded">错误</span>
                            )}
                          </div>
                          
                          <div className="mb-3">
                            <div className="text-xs text-gray-500 mb-1">您的答案：</div>
                            <div className={`text-sm p-3 rounded-lg ${
                              question.type === 'code' ? 'bg-gray-900 text-gray-100 font-mono' : 'bg-white'
                            }`}>
                              {question.answer}
                            </div>
                          </div>

                          {question.comment && (
                            <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
                              <div className="text-xs text-blue-600 font-medium mb-1">教师评语：</div>
                              <div className="text-sm text-gray-700">{question.comment}</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {currentHomework.teacherComment && (
                    <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <div className="flex items-start gap-2">
                        <i className="ri-message-3-line text-yellow-600 text-lg flex-shrink-0 mt-0.5"></i>
                        <div>
                          <div className="text-sm font-semibold text-gray-900 mb-1">教师总评</div>
                          <div className="text-sm text-gray-700">{currentHomework.teacherComment}</div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end flex-shrink-0">
                <button
                  onClick={() => {
                    setShowGradingModal(false);
                    setCurrentHomework(null);
                  }}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 错题详情弹窗 */}
        {showMistakeDetailModal && currentMistake && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">错题详情</h2>
                <button
                  onClick={() => {
                    setShowMistakeDetailModal(false);
                    setCurrentMistake(null);
                    setCurrentMistakePractice(null);
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-5">
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">题目</div>
                    <div className="text-sm text-gray-700 p-3 bg-gray-50 rounded-lg">{currentMistake.question}</div>
                  </div>

                  {currentMistakePractice && currentMistakePractice.mistakeId === currentMistake.id && (
                    <div className="p-4 bg-teal-50 border border-teal-100 rounded-lg">
                      <div className="text-sm font-semibold text-teal-800 mb-2">本次练习</div>
                      <div className="text-sm text-gray-800 whitespace-pre-line leading-relaxed">
                        {currentMistakePractice.prompt}
                      </div>
                    </div>
                  )}

                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">所属章节</div>
                    <div className="text-sm text-gray-700">{currentMistake.chapter}</div>
                  </div>

                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">我的答案</div>
                    <div className="text-sm text-red-600 p-3 bg-red-50 border border-red-100 rounded-lg">
                      {currentMistake.myAnswer}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">正确答案</div>
                    <div className="text-sm text-green-600 p-3 bg-green-50 border border-green-100 rounded-lg">
                      {currentMistake.correctAnswer}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">解析</div>
                    <div className="text-sm text-gray-700 p-3 bg-blue-50 border border-blue-100 rounded-lg leading-relaxed">
                      {currentMistake.analysis}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <div className="text-xs text-gray-500 mb-1">错误次数</div>
                      <div className="text-lg font-bold text-red-600">{currentMistake.wrongCount}次</div>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <div className="text-xs text-gray-500 mb-1">添加时间</div>
                      <div className="text-sm text-gray-900">{currentMistake.addTime}</div>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <div className="text-xs text-gray-500 mb-1">最后练习</div>
                      <div className="text-sm text-gray-900">{currentMistake.lastPracticeTime}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    setShowMistakeDetailModal(false);
                    setCurrentMistake(null);
                    setCurrentMistakePractice(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
                <button
                  onClick={() => handlePracticeMistake(currentMistake)}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  重新练习
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 添加错题弹窗 */}
        {showAddMistakeModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">添加错题</h2>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">题目 *</label>
                    <textarea
                      rows={3}
                      value={newMistakeForm.question}
                      onChange={(e) => setNewMistakeForm({ ...newMistakeForm, question: e.target.value })}
                      placeholder="请输入题目内容..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">所属章节 *</label>
                    <input
                      type="text"
                      value={newMistakeForm.chapter}
                      onChange={(e) => setNewMistakeForm({ ...newMistakeForm, chapter: e.target.value })}
                      placeholder="例如：第5章 传输层"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">我的答案</label>
                    <textarea
                      rows={3}
                      value={newMistakeForm.myAnswer}
                      onChange={(e) => setNewMistakeForm({ ...newMistakeForm, myAnswer: e.target.value })}
                      placeholder="请输入您的错误答案..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">正确答案</label>
                    <textarea
                      rows={3}
                      value={newMistakeForm.correctAnswer}
                      onChange={(e) => setNewMistakeForm({ ...newMistakeForm, correctAnswer: e.target.value })}
                      placeholder="请输入正确答案..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">解析</label>
                    <textarea
                      rows={4}
                      value={newMistakeForm.analysis}
                      onChange={(e) => setNewMistakeForm({ ...newMistakeForm, analysis: e.target.value })}
                      placeholder="请输入题目解析..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    setShowAddMistakeModal(false);
                    setNewMistakeForm(createEmptyMistakeForm());
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  onClick={handleAddMistake}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  确认添加
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 添加提问弹窗 */}
        {showAddQuestionModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">添加提问</h2>
              </div>
              
              <div className="px-6 py-5 overflow-y-auto flex-1">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">问题标题 *</label>
                    <input
                      type="text"
                      value={newQuestionForm.title}
                      onChange={(e) => setNewQuestionForm({ ...newQuestionForm, title: e.target.value })}
                      placeholder="请输入问题标题"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">问题描述 *</label>
                    <textarea
                      rows={6}
                      value={newQuestionForm.content}
                      onChange={(e) => setNewQuestionForm({ ...newQuestionForm, content: e.target.value })}
                      placeholder="请详细描述您的问题..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  {/* 附件上传区域 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">附件（可选）</label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center">
                      <input
                        ref={questionAttachmentRef}
                        type="file"
                        multiple
                        onChange={handleQuestionAttachmentUpload}
                        className="hidden"
                      />
                      <button
                        onClick={() => questionAttachmentRef.current?.click()}
                        className="px-4 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-attachment-line mr-1"></i>添加附件
                      </button>
                      <p className="text-xs text-gray-500 mt-2">支持图片、文档等格式</p>
                    </div>
                    
                    {/* 附件列表 */}
                    {newQuestionForm.attachments.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {newQuestionForm.attachments.map((file, index) => (
                          <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                            <i className="ri-file-line text-gray-400"></i>
                            <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                            <span className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</span>
                            <button
                              onClick={() => removeQuestionAttachment(index)}
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
                    setShowAddQuestionModal(false);
                    setNewQuestionForm(createEmptyQuestionForm());
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  onClick={handleAddQuestion}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  提交提问
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 发起讨论弹窗 */}
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
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  发布讨论
                </button>
              </div>
            </div>
          </div>
        )}

        {/* AI转人工申请弹窗 */}
        {showAIToTeacherModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">申请教师解答</h2>
              </div>
              
              <div className="px-6 py-5 overflow-y-auto flex-1">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">问题标题 *</label>
                    <input
                      type="text"
                      value={aiToTeacherForm.title}
                      onChange={(e) => setAiToTeacherForm({ ...aiToTeacherForm, title: e.target.value })}
                      placeholder="请输入问题标题"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">问题描述 *</label>
                    <textarea
                      rows={4}
                      value={aiToTeacherForm.content}
                      onChange={(e) => setAiToTeacherForm({ ...aiToTeacherForm, content: e.target.value })}
                      placeholder="请详细描述您的问题..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">AI的回答（可选）</label>
                    <textarea
                      rows={3}
                      value={aiToTeacherForm.aiAnswer}
                      onChange={(e) => setAiToTeacherForm({ ...aiToTeacherForm, aiAnswer: e.target.value })}
                      placeholder="如果AI已经给出回答，可以粘贴在这里..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">申请原因 *</label>
                    <textarea
                      rows={3}
                      value={aiToTeacherForm.reason}
                      onChange={(e) => setAiToTeacherForm({ ...aiToTeacherForm, reason: e.target.value })}
                      placeholder="请说明为什么需要教师介入解答..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>

                  <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                    <div className="flex items-start gap-2">
                      <i className="ri-information-line text-blue-600 text-base flex-shrink-0 mt-0.5"></i>
                      <div className="text-xs text-blue-700">
                        <div className="font-medium mb-1">温馨提示</div>
                        <div>教师会在收到申请后尽快为您解答。请耐心等待，通常会在24小时内得到回复。</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    setShowAIToTeacherModal(false);
                    setAiToTeacherForm(createEmptyAiToTeacherForm());
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  onClick={handleAIToTeacherRequest}
                  className="px-6 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  提交申请
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 创建卡组弹窗 */}
        {showCreateDeckModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">创建卡组</h2>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">卡组名称 *</label>
                    <input
                      type="text"
                      value={newDeckForm.name}
                      onChange={(e) => setNewDeckForm({ ...newDeckForm, name: e.target.value })}
                      placeholder="例如：第6章 应用层"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <label className="block text-sm font-medium text-gray-700">卡片内容</label>
                      <button
                        onClick={handleAddCardToForm}
                        className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-add-line mr-1"></i>添加卡片
                      </button>
                    </div>
                    
                    <div className="space-y-4">
                      {newDeckForm.cards.map((card, index) => (
                        <div key={index} className="p-4 border border-gray-200 rounded-lg">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-medium text-gray-900">卡片 {index + 1}</span>
                            {newDeckForm.cards.length > 1 && (
                              <button
                                onClick={() => handleRemoveCardFromForm(index)}
                                className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-600 cursor-pointer"
                              >
                                <i className="ri-delete-bin-line"></i>
                              </button>
                            )}
                          </div>
                          <div className="space-y-3">
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">正面（问题）</label>
                              <textarea
                                rows={2}
                                value={card.front}
                                onChange={(e) => handleUpdateCardInForm(index, 'front', e.target.value)}
                                placeholder="输入问题..."
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                              ></textarea>
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">背面（答案）</label>
                              <textarea
                                rows={3}
                                value={card.back}
                                onChange={(e) => handleUpdateCardInForm(index, 'back', e.target.value)}
                                placeholder="输入答案..."
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                              ></textarea>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    setShowCreateDeckModal(false);
                    setNewDeckForm(createEmptyDeckForm());
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  onClick={handleCreateDeck}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  创建卡组
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 复习/学习卡片弹窗 */}
        {(showReviewModal || showStudyModal) && currentDeck && currentDeck.cardList.length > 0 && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-2xl overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{currentDeck.name}</h2>
                  <div className="text-sm text-gray-500 mt-1">
                    卡片 {currentCardIndex + 1} / {currentDeck.cardList.length}
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowReviewModal(false);
                    setShowStudyModal(false);
                    setCurrentDeck(null);
                    setCurrentCardIndex(0);
                    setIsCardFlipped(false);
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="p-8">
                {/* 卡片 */}
                <div 
                  onClick={handleFlipCard}
                  className="relative bg-gradient-to-br from-teal-50 to-blue-50 rounded-xl p-8 min-h-[300px] flex items-center justify-center cursor-pointer hover:shadow-lg transition-all border-2 border-teal-200"
                  style={{ perspective: '1000px' }}
                >
                  <div className="text-center">
                    {!isCardFlipped ? (
                      <>
                        <div className="text-xs font-medium text-teal-600 mb-3">问题</div>
                        <div className="text-lg font-medium text-gray-900 leading-relaxed whitespace-pre-line">
                          {currentDeck.cardList[currentCardIndex].front}
                        </div>
                        <div className="mt-6 text-sm text-gray-500">
                          <i className="ri-refresh-line mr-1"></i>点击翻转查看答案
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="text-xs font-medium text-blue-600 mb-3">答案</div>
                        <div className="text-base text-gray-800 leading-relaxed whitespace-pre-line">
                          {currentDeck.cardList[currentCardIndex].back}
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* 回答按钮 */}
                {isCardFlipped && (
                  <div className="mt-6">
                    <div className="text-sm text-gray-600 text-center mb-3">根据您的掌握程度选择：</div>
                    <div className="grid grid-cols-4 gap-3">
                      <button
                        onClick={() => handleAnswerCard('forget')}
                        className="flex flex-col items-center gap-2 p-4 bg-red-50 border-2 border-red-200 rounded-lg hover:bg-red-100 cursor-pointer transition-colors"
                      >
                        <i className="ri-close-line text-2xl text-red-600"></i>
                        <span className="text-sm font-medium text-red-700">忘记</span>
                        <span className="text-xs text-red-600">1天后</span>
                      </button>
                      <button
                        onClick={() => handleAnswerCard('hard')}
                        className="flex flex-col items-center gap-2 p-4 bg-orange-50 border-2 border-orange-200 rounded-lg hover:bg-orange-100 cursor-pointer transition-colors"
                      >
                        <i className="ri-question-line text-2xl text-orange-600"></i>
                        <span className="text-sm font-medium text-orange-700">模糊</span>
                        <span className="text-xs text-orange-600">2天后</span>
                      </button>
                      <button
                        onClick={() => handleAnswerCard('good')}
                        className="flex flex-col items-center gap-2 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg hover:bg-blue-100 cursor-pointer transition-colors"
                      >
                        <i className="ri-check-line text-2xl text-blue-600"></i>
                        <span className="text-sm font-medium text-blue-700">记得</span>
                        <span className="text-xs text-blue-600">6天后</span>
                      </button>
                      <button
                        onClick={() => handleAnswerCard('easy')}
                        className="flex flex-col items-center gap-2 p-4 bg-green-50 border-2 border-green-200 rounded-lg hover:bg-green-100 cursor-pointer transition-colors"
                      >
                        <i className="ri-thumb-up-line text-2xl text-green-600"></i>
                        <span className="text-sm font-medium text-green-700">简单</span>
                        <span className="text-xs text-green-600">15天后</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* 进度条 */}
              <div className="px-6 pb-4">
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-teal-500 rounded-full transition-all duration-300"
                    style={{ width: `${((currentCardIndex + 1) / currentDeck.cardList.length) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        )}


      </main>
    </div>
  );
}
