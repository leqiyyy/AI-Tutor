import { useState, useRef, useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import AIAssistant from './components/AIAssistant';

export default function StudentCourse() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [activeSection, setActiveSection] = useState('home');
  const [highlightedTaskId, setHighlightedTaskId] = useState<string | null>(null);
  const [highlightedChapterId, setHighlightedChapterId] = useState<string | null>(null);

  // 新增：课程资料相关状态
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [showAIAnalysisModal, setShowAIAnalysisModal] = useState(false);
  const [showKnowledgeGraphModal, setShowKnowledgeGraphModal] = useState(false);
  const [currentFile, setCurrentFile] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [videoSpeed, setVideoSpeed] = useState('1.0');
  const [expandedGraphNodes, setExpandedGraphNodes] = useState<string[]>(['root']);
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement>(null);

  // 新增：任务中心相关状态
  const [taskFilter, setTaskFilter] = useState('all');
  const [showHomeworkModal, setShowHomeworkModal] = useState(false);
  const [showGradingModal, setShowGradingModal] = useState(false);
  const [currentHomework, setCurrentHomework] = useState<any>(null);
  const [homeworkAnswers, setHomeworkAnswers] = useState<Record<number, string>>({});
  const [showMistakeDetailModal, setShowMistakeDetailModal] = useState(false);
  const [showAddMistakeModal, setShowAddMistakeModal] = useState(false);
  const [currentMistake, setCurrentMistake] = useState<any>(null);
  const [mistakeFilter, setMistakeFilter] = useState('all');
  const [newMistakeForm, setNewMistakeForm] = useState({
    question: '',
    chapter: '',
    myAnswer: '',
    correctAnswer: '',
    analysis: ''
  });

  // 新增：互动空间相关状态
  const [expandedQuestions, setExpandedQuestions] = useState<number[]>([]);
  const [replyingToQuestion, setReplyingToQuestion] = useState<number | null>(null);
  const [questionReplyContent, setQuestionReplyContent] = useState('');
  const [showAddQuestionModal, setShowAddQuestionModal] = useState(false);
  const [newQuestionForm, setNewQuestionForm] = useState({
    title: '',
    content: '',
    attachments: [] as File[]
  });
  const [myQuestions, setMyQuestions] = useState([
    {
      id: 1,
      title: 'TCP三次握手的第三次可以携带数据吗?',
      content: '老师您好，我在学习TCP协议时，看到资料说第三次握手可以携带数据，但不太理解为什么前两次不能携带数据。能否详细解释一下原因？',
      time: '2024-03-18 10:30',
      status: 'answered',
      replies: [
        {
          author: '王教授',
          content: '是的，TCP三次握手的第三次握手可以携带数据。\n\n原因如下：\n• 第一次握手（SYN）：客户端发送SYN报文，此时连接尚未建立，不能携带数据\n• 第二次握手（SYN+ACK）：服务器回复SYN+ACK报文，连接仍未完全建立，不能携带数据\n• 第三次握手（ACK）：客户端发送ACK报文，此时连接已建立，可以携带数据\n\n这是因为前两次握手时连接尚未完全建立，而第三次握手时客户端已经确认服务器的接收能力，连接进入ESTABLISHED状态，因此可以开始传输应用层数据。',
          time: '2024-03-18 14:20',
          isTeacher: true
        }
      ]
    },
    {
      id: 2,
      title: '红黑树的左旋和右旋操作具体是如何实现的?',
      content: '在学习红黑树时，对左旋和右旋操作的具体实现不太理解，能否提供一个详细的图解或代码示例？',
      time: '2024-03-17 15:45',
      status: 'pending',
      replies: []
    },
    {
      id: 3,
      title: 'HTTP和HTTPS的主要区别是什么?',
      content: '除了加密之外，HTTP和HTTPS在性能、端口等方面还有哪些区别？',
      time: '2024-03-16 09:20',
      status: 'answered',
      replies: [
        {
          author: '王教授',
          content: 'HTTP与HTTPS的主要区别包括：\n\n1. 安全性：HTTP是明文传输，HTTPS通过TLS/SSL加密传输\n2. 端口：HTTP默认使用80端口，HTTPS默认使用443端口\n3. 证书：HTTPS需要CA颁发的数字证书\n4. 性能：HTTPS因加密解密有轻微性能开销\n5. SEO：搜索引擎对HTTPS站点有更高的排名权重',
          time: '2024-03-16 16:30',
          isTeacher: true
        }
      ]
    }
  ]);

  const [expandedDiscussions, setExpandedDiscussions] = useState<number[]>([]);
  const [replyingToDiscussion, setReplyingToDiscussion] = useState<number | null>(null);
  const [discussionReplyContent, setDiscussionReplyContent] = useState('');
  const [showNewDiscussionModal, setShowNewDiscussionModal] = useState(false);
  const [newDiscussionForm, setNewDiscussionForm] = useState({
    title: '',
    content: ''
  });
  const [discussions, setDiscussions] = useState([
    {
      id: 1,
      student: '张三',
      title: '关于OSI七层模型的理解',
      content: '老师您好，我在学习OSI七层模型时，对于传输层和网络层的区别有些疑惑。传输层的TCP协议和网络层的IP协议在数据传输中分别起什么作用？它们之间是如何协作的？希望老师能详细讲解一下。',
      replies: [
        {
          author: '李四',
          content: '我也有同样的疑问，期待老师解答！',
          time: '1小时前',
          isStudent: true
        },
        {
          author: '王五',
          content: '我觉得传输层主要负责端到端的可靠传输，网络层负责路由选择。',
          time: '50分钟前',
          isStudent: true
        }
      ],
      likes: 8,
      time: '2小时前',
      liked: false
    },
    {
      id: 2,
      student: '李四',
      title: '路由算法的实际应用场景',
      content: '在课堂上学习了Dijkstra算法和Bellman-Ford算法，想请教老师这两种算法在实际网络中的应用场景有什么区别？哪种算法更适合大规模网络？',
      replies: [],
      likes: 5,
      time: '5小时前',
      liked: false
    },
    {
      id: 3,
      student: '王五',
      title: 'TCP拥塞控制机制讨论',
      content: 'TCP的拥塞控制包括慢启动、拥塞避免、快重传和快恢复四个阶段。我想和大家讨论一下，在实际网络环境中，这些机制是如何协同工作的？',
      replies: [
        {
          author: '赵六',
          content: '我认为慢启动阶段是指数增长，拥塞避免是线性增长，这样可以快速探测网络容量同时避免过度拥塞。',
          time: '3小时前',
          isStudent: true
        }
      ],
      likes: 3,
      time: '1天前',
      liked: false
    }
  ]);

  const [expandedFAQs, setExpandedFAQs] = useState<number[]>([]);
  const [faqs, setFaqs] = useState([
    {
      id: 1,
      title: '第5章高频问题解答',
      date: '2024-03-10',
      views: 156,
      content: '本次集中答疑主要针对第5章传输层的高频问题进行解答：\n\n1. TCP三次握手和四次挥手的详细过程\n2. TCP拥塞控制算法的工作原理\n3. UDP协议的应用场景\n4. 滑动窗口机制的实现细节\n\n详细内容请查看附件文档。',
      attachments: ['第5章答疑汇总.pdf']
    },
    {
      id: 2,
      title: 'TCP协议常见疑问',
      date: '2024-03-05',
      views: 142,
      content: '针对同学们在学习TCP协议时遇到的常见问题进行统一解答：\n\n1. 为什么需要三次握手？两次不行吗？\n2. TIME_WAIT状态的作用是什么？\n3. TCP如何保证可靠传输？\n4. 粘包问题如何解决？',
      attachments: []
    },
    {
      id: 3,
      title: '期中考试答疑汇总',
      date: '2024-02-28',
      views: 189,
      content: '期中考试前的集中答疑内容汇总，包括：\n\n1. 各层协议的主要功能\n2. 常见网络设备的工作层次\n3. 子网划分的计算方法\n4. 路由算法的比较',
      attachments: ['期中考试复习要点.pdf', '历年真题解析.pdf']
    }
  ]);

  const [showAIToTeacherModal, setShowAIToTeacherModal] = useState(false);
  const [aiToTeacherForm, setAiToTeacherForm] = useState({
    title: '',
    content: '',
    aiAnswer: '',
    reason: ''
  });

  const questionAttachmentRef = useRef<HTMLInputElement>(null);

  // 模拟作业数据
  const [homeworks, setHomeworks] = useState([
    { 
      id: 'hw-tree-binary', 
      title: '第5章树与二叉树课后作业', 
      deadline: '今天 23:59', 
      status: 'pending', 
      score: null, 
      urgent: true,
      questions: [
        { id: 1, content: '请简述二叉树的三种遍历方式（前序、中序、后序）的区别。', type: 'text', answer: '' },
        { id: 2, content: '什么是完全二叉树？请画图说明。', type: 'text', answer: '' },
        { id: 3, content: '红黑树的五个性质是什么？', type: 'text', answer: '' }
      ]
    },
    { 
      id: 'hw-graph', 
      title: '第4章图论算法实现', 
      deadline: '明天 23:59', 
      status: 'pending', 
      score: null, 
      urgent: false,
      questions: [
        { id: 1, content: '请用代码实现图的深度优先遍历（DFS）。', type: 'code', answer: '' },
        { id: 2, content: '请用代码实现图的广度优先遍历（BFS）。', type: 'code', answer: '' }
      ]
    },
    { 
      id: 'exam-midterm-os', 
      title: '操作系统期中考试', 
      deadline: '明天 14:00', 
      status: 'pending', 
      score: null, 
      urgent: false, 
      isExam: true,
      questions: []
    },
    { 
      id: 'hw-stack-queue', 
      title: '第3章栈和队列练习', 
      deadline: '2024-03-15', 
      status: 'submitted', 
      score: null, 
      urgent: false,
      questions: []
    },
    { 
      id: 'hw-linear-list', 
      title: '第2章线性表编程题', 
      deadline: '2024-03-10', 
      status: 'graded', 
      score: 88, 
      urgent: false,
      questions: [
        { id: 1, content: '请实现单链表的插入操作。', type: 'code', answer: 'function insert(head, value) { ... }', correct: true, comment: '实现正确，代码规范' },
        { id: 2, content: '请实现单链表的删除操作。', type: 'code', answer: 'function delete(head, value) { ... }', correct: false, comment: '边界条件处理不完善，需要考虑删除头节点的情况' },
        { id: 3, content: '请实现单链表的反转操作。', type: 'code', answer: 'function reverse(head) { ... }', correct: true, comment: '实现正确，思路清晰' }
      ],
      teacherComment: '整体完成较好，但需要注意边界条件的处理。建议多做一些链表相关的练习题。'
    },
    { 
      id: 'hw-complexity', 
      title: '第1章算法复杂度分析', 
      deadline: '2024-03-05', 
      status: 'graded', 
      score: 95, 
      urgent: false,
      questions: [
        { id: 1, content: '请分析冒泡排序的时间复杂度。', type: 'text', answer: 'O(n^2)', correct: true, comment: '分析正确' },
        { id: 2, content: '请分析快速排序的平均时间复杂度。', type: 'text', answer: 'O(nlogn)', correct: true, comment: '分析正确' }
      ],
      teacherComment: '非常好！对算法复杂度的理解很到位。'
    }
  ]);

  // 模拟错题本数据
  const [mistakes, setMistakes] = useState([
    { 
      id: 1, 
      question: 'TCP三次握手过程中，第二次握手发送的标志位是？', 
      chapter: '第5章 传输层', 
      wrongCount: 2,
      myAnswer: 'SYN',
      correctAnswer: 'SYN+ACK',
      analysis: '第二次握手时，服务器需要同时发送SYN和ACK标志位，表示同意建立连接并确认收到客户端的SYN。',
      addTime: '2024-03-10',
      lastPracticeTime: '2024-03-15',
      mastered: false
    },
    { 
      id: 2, 
      question: '红黑树的左旋和右旋操作具体是如何实现的？', 
      chapter: '第7章 树', 
      wrongCount: 1,
      myAnswer: '将节点向左移动',
      correctAnswer: '左旋是将节点的右子节点提升为新的根节点，原节点成为新根的左子节点；右旋相反。',
      analysis: '旋转操作是红黑树保持平衡的关键。左旋和右旋是对称的操作，需要正确处理节点之间的指针关系。',
      addTime: '2024-03-12',
      lastPracticeTime: '2024-03-16',
      mastered: false
    },
    { 
      id: 3, 
      question: '进程调度算法中，时间片轮转的优缺点是？', 
      chapter: '第4章 进程管理', 
      wrongCount: 1,
      myAnswer: '优点是公平，缺点是效率低',
      correctAnswer: '优点：公平性好，响应时间短；缺点：上下文切换开销大，时间片大小难以确定。',
      analysis: '时间片轮转算法是一种抢占式调度算法，需要权衡公平性和效率。时间片太小会导致频繁切换，太大则退化为先来先服务。',
      addTime: '2024-03-08',
      lastPracticeTime: '2024-03-14',
      mastered: true
    }
  ]);

  // 新增：学习闪卡相关状态
  const [showCreateDeckModal, setShowCreateDeckModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showStudyModal, setShowStudyModal] = useState(false);
  const [currentDeck, setCurrentDeck] = useState<any>(null);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isCardFlipped, setIsCardFlipped] = useState(false);
  const [newDeckForm, setNewDeckForm] = useState({
    name: '',
    cards: [{ front: '', back: '' }]
  });
  const [decks, setDecks] = useState([
    { id: 1, name: '第5章 传输层', cards: 45, mastered: 32, learning: 10, new: 3, nextReview: '今天', cardList: [
      { front: 'TCP三次握手的三个步骤是什么？', back: '1. SYN：客户端发送SYN报文\n2. SYN+ACK：服务器回复SYN+ACK报文\n3. ACK：客户端发送ACK报文，连接建立' },
      { front: 'TCP拥塞控制的四个算法是什么？', back: '1. 慢启动（Slow Start）\n2. 拥塞避免（Congestion Avoidance）\n3. 快速重传（Fast Retransmit）\n4. 快速恢复（Fast Recovery）' },
      { front: 'UDP协议的特点有哪些？', back: '1. 无连接\n2. 不可靠传输\n3. 面向报文\n4. 无拥塞控制\n5. 支持一对一、一对多、多对多通信' }
    ]},
    { id: 2, name: '第4章 网络层', cards: 38, mastered: 28, learning: 8, new: 2, nextReview: '明天', cardList: [
      { front: 'IP地址分为哪几类？', back: 'A类：1.0.0.0 ~ 126.255.255.255\nB类：128.0.0.0 ~ 191.255.255.255\nC类：192.0.0.0 ~ 223.255.255.255\nD类：224.0.0.0 ~ 239.255.255.255（组播）\nE类：240.0.0.0 ~ 255.255.255.255（保留）' },
      { front: '子网掩码的作用是什么？', back: '子网掩码用于将IP地址划分为网络部分和主机部分，通过与IP地址进行按位与运算，可以得到网络地址。' }
    ]},
    { id: 3, name: '第3章 数据链路层', cards: 42, mastered: 35, learning: 5, new: 2, nextReview: '2天后', cardList: [] },
    { id: 4, name: 'TCP协议专题', cards: 28, mastered: 20, learning: 6, new: 2, nextReview: '今天', cardList: [] },
    { id: 5, name: '路由算法', cards: 25, mastered: 18, learning: 5, new: 2, nextReview: '3天后', cardList: [] },
    { id: 6, name: '我的自定义卡组', cards: 15, mastered: 8, learning: 5, new: 2, nextReview: '今天', cardList: [] }
  ]);

  // 新增：我的学习相关状态
  const [showWeeklyReportModal, setShowWeeklyReportModal] = useState(false);
  const [showMonthlyReportModal, setShowMonthlyReportModal] = useState(false);
  const [showExportDataModal, setShowExportDataModal] = useState(false);
  const [exportFormat, setExportFormat] = useState('csv');
  const [exportFields, setExportFields] = useState({
    studyTime: true,
    homework: true,
    aiQuestions: true,
    attendance: true,
    grades: true
  });

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
  const handlePreviewFile = (file: any) => {
    setCurrentFile(file);
    setShowPreviewModal(true);
    
    // 预留后端接口：获取文件预览URL
    console.log('获取文件预览API调用:', { fileId: file.id });
  };

  // 新增：下载文件
  const handleDownloadFile = (file: any) => {
    // 预留后端接口：下载文件
    console.log('下载文件API调用:', { fileId: file.id });
    
    // 模拟下载
    alert(`正在下载 ${file.name}...`);
  };

  // 新增：AI解析文件
  const handleAIAnalysis = (file: any) => {
    setCurrentFile(file);
    setShowAIAnalysisModal(true);
    
    // 预留后端接口：获取AI解析结果
    console.log('获取AI解析结果API调用:', { fileId: file.id });
  };

  // 新增：打开知识图谱
  const handleOpenKnowledgeGraph = () => {
    setShowKnowledgeGraphModal(true);
    
    // 预留后端接口：获取知识图谱数据
    console.log('获取知识图谱数据API调用:', { courseId: id });
  };

  // 新增：全文搜索
  const handleSearch = () => {
    if (!searchQuery.trim()) return;
    
    // 预留后端接口：全文搜索
    console.log('全文搜索API调用:', { courseId: id, query: searchQuery });
    
    alert(`搜索结果：找到 ${Math.floor(Math.random() * 20) + 1} 条相关内容`);
  };

  // 新增：切换知识图谱节点
  const toggleGraphNode = (nodeId: string) => {
    setExpandedGraphNodes(prev => 
      prev.includes(nodeId) 
        ? prev.filter(id => id !== nodeId)
        : [...prev, nodeId]
    );
  };

  // 新增：重置知识图谱
  const resetGraph = () => {
    setExpandedGraphNodes(['root']);
    setIsGraphFullscreen(false);
  };

  // 新增：切换知识图谱全屏
  const toggleGraphFullscreen = () => {
    if (!isGraphFullscreen) {
      graphContainerRef.current?.requestFullscreen();
      setIsGraphFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsGraphFullscreen(false);
    }
  };

  // 监听全屏变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsGraphFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // 知识图谱节点数据
  const graphNodes = [
    { id: 'root', label: '计算机网络', x: 400, y: 50, parent: null, color: '#14b8a6' },
    { id: 'physical', label: '物理层', x: 200, y: 150, parent: 'root', color: '#3b82f6' },
    { id: 'datalink', label: '数据链路层', x: 350, y: 150, parent: 'root', color: '#10b981' },
    { id: 'network', label: '网络层', x: 500, y: 150, parent: 'root', color: '#8b5cf6' },
    { id: 'transport', label: '传输层', x: 650, y: 150, parent: 'root', color: '#f59e0b' },
    { id: 'application', label: '应用层', x: 800, y: 150, parent: 'root', color: '#ec4899' },
    { id: 'tcp', label: 'TCP协议', x: 600, y: 250, parent: 'transport', color: '#f59e0b' },
    { id: 'udp', label: 'UDP协议', x: 700, y: 250, parent: 'transport', color: '#f59e0b' },
    { id: 'ip', label: 'IP协议', x: 450, y: 250, parent: 'network', color: '#8b5cf6' },
    { id: 'routing', label: '路由算法', x: 550, y: 250, parent: 'network', color: '#8b5cf6' },
    { id: 'http', label: 'HTTP', x: 750, y: 250, parent: 'application', color: '#ec4899' },
    { id: 'dns', label: 'DNS', x: 850, y: 250, parent: 'application', color: '#ec4899' },
  ];

  // 获取可见的知识图谱节点
  const getVisibleGraphNodes = () => {
    const visible = graphNodes.filter(node => {
      if (node.parent === null) return true;
      return expandedGraphNodes.includes(node.parent);
    });
    return visible;
  };

  // 模拟课程数据
  const courseData = {
    1: { name: '计算机网络', teacher: '王教授', code: 'CS301' },
    2: { name: '数据结构与算法', teacher: '李教授', code: 'CS201' },
    3: { name: '操作系统原理', teacher: '张教授', code: 'CS302' },
    4: { name: '数据库系统', teacher: '刘教授', code: 'CS303' },
    5: { name: '软件工程', teacher: '陈教授', code: 'CS401' }
  };

  const course = courseData[id as keyof typeof courseData] || { name: '未知课程', teacher: '未知教师', code: 'UNKNOWN' };

  // 新增：获取过滤后的任务列表
  const getFilteredHomeworks = () => {
    if (taskFilter === 'all') return homeworks;
    if (taskFilter === 'pending') return homeworks.filter(hw => hw.status === 'pending');
    if (taskFilter === 'submitted') return homeworks.filter(hw => hw.status === 'submitted');
    if (taskFilter === 'graded') return homeworks.filter(hw => hw.status === 'graded');
    if (taskFilter === 'overdue') {
      // 模拟逾期判断
      return homeworks.filter(hw => hw.status === 'pending' && hw.deadline.includes('2024'));
    }
    return homeworks;
  };

  // 新增：开始作业
  const handleStartHomework = (homework: any) => {
    setCurrentHomework(homework);
    setHomeworkAnswers({});
    setShowHomeworkModal(true);
    
    // 预留后端接口：获取作业详情
    console.log('获取作业详情API调用:', { homeworkId: homework.id });
  };

  // 新增：提交作业
  const handleSubmitHomework = () => {
    if (Object.keys(homeworkAnswers).length < currentHomework.questions.length) {
      alert('请完成所有题目后再提交');
      return;
    }

    // 预留后端接口：提交作业
    console.log('提交作业API调用:', {
      homeworkId: currentHomework.id,
      answers: homeworkAnswers
    });

    // 更新作业状态
    setHomeworks(prev => prev.map(hw => 
      hw.id === currentHomework.id ? { ...hw, status: 'submitted' } : hw
    ));

    alert('作业提交成功！等待教师批改。');
    setShowHomeworkModal(false);
    setCurrentHomework(null);
    setHomeworkAnswers({});
  };

  // 新增：查看批改
  const handleViewGrading = (homework: any) => {
    setCurrentHomework(homework);
    setShowGradingModal(true);
    
    // 预留后端接口：获取批改结果
    console.log('获取批改结果API调用:', { homeworkId: homework.id });
  };

  // 新增：获取过滤后的错题列表
  const getFilteredMistakes = () => {
    if (mistakeFilter === 'all') return mistakes;
    if (mistakeFilter === 'unmastered') return mistakes.filter(m => !m.mastered);
    if (mistakeFilter === 'mastered') return mistakes.filter(m => m.mastered);
    return mistakes;
  };

  // 新增：查看错题详情
  const handleViewMistake = (mistake: any) => {
    setCurrentMistake(mistake);
    setShowMistakeDetailModal(true);
  };

  // 新增：重新练习错题
  const handlePracticeMistake = (mistake: any) => {
    // 预留后端接口：开始练习错题
    console.log('开始练习错题API调用:', { mistakeId: mistake.id });
    
    alert(`开始练习：${mistake.question}`);
  };

  // 新增：标记错题为已掌握
  const handleMarkMastered = (mistakeId: number) => {
    setMistakes(prev => prev.map(m => 
      m.id === mistakeId ? { ...m, mastered: true, lastPracticeTime: new Date().toISOString().split('T')[0] } : m
    ));
    
    // 预留后端接口：更新错题状态
    console.log('更新错题状态API调用:', { mistakeId, mastered: true });
  };

  // 新增：添加错题
  const handleAddMistake = () => {
    if (!newMistakeForm.question.trim() || !newMistakeForm.chapter.trim()) {
      alert('请至少填写题目和章节');
      return;
    }

    const newMistake = {
      id: Date.now(),
      question: newMistakeForm.question,
      chapter: newMistakeForm.chapter,
      wrongCount: 1,
      myAnswer: newMistakeForm.myAnswer,
      correctAnswer: newMistakeForm.correctAnswer,
      analysis: newMistakeForm.analysis,
      addTime: new Date().toISOString().split('T')[0],
      lastPracticeTime: new Date().toISOString().split('T')[0],
      mastered: false
    };

    setMistakes([newMistake, ...mistakes]);

    // 预留后端接口：添加错题
    console.log('添加错题API调用:', newMistake);

    alert('错题添加成功！');
    setShowAddMistakeModal(false);
    setNewMistakeForm({
      question: '',
      chapter: '',
      myAnswer: '',
      correctAnswer: '',
      analysis: ''
    });
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
  const submitQuestionReply = (questionId: number) => {
    if (!questionReplyContent.trim()) return;

    const now = new Date();
    const timeStr = `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}-${now.getDate().toString().padStart(2, '0')} ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    setMyQuestions(prev => prev.map(q => {
      if (q.id === questionId) {
        return {
          ...q,
          replies: [...q.replies, {
            author: '我',
            content: questionReplyContent,
            time: timeStr,
            isTeacher: false
          }]
        };
      }
      return q;
    }));

    // 预留后端接口
    console.log('提交问题回复API调用:', {
      questionId,
      content: questionReplyContent
    });

    setReplyingToQuestion(null);
    setQuestionReplyContent('');
  };

  // 新增：添加新提问
  const handleAddQuestion = () => {
    if (!newQuestionForm.title.trim() || !newQuestionForm.content.trim()) {
      alert('请填写完整的提问标题和内容');
      return;
    }

    const now = new Date();
    const timeStr = `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}-${now.getDate().toString().padStart(2, '0')} ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    const newQuestion = {
      id: Date.now(),
      title: newQuestionForm.title,
      content: newQuestionForm.content,
      time: timeStr,
      status: 'pending' as const,
      replies: []
    };

    setMyQuestions([newQuestion, ...myQuestions]);

    // 预留后端接口
    console.log('添加新提问API调用:', {
      title: newQuestionForm.title,
      content: newQuestionForm.content,
      attachments: newQuestionForm.attachments
    });

    alert('提问提交成功！等待教师回复。');
    setShowAddQuestionModal(false);
    setNewQuestionForm({ title: '', content: '', attachments: [] });
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
  const submitDiscussionReply = (discussionId: number) => {
    if (!discussionReplyContent.trim()) return;

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    setDiscussions(prev => prev.map(d => {
      if (d.id === discussionId) {
        return {
          ...d,
          replies: [...d.replies, {
            author: '我',
            content: discussionReplyContent,
            time: `${timeStr}`,
            isStudent: true
          }]
        };
      }
      return d;
    }));

    // 预留后端接口
    console.log('提交讨论回复API调用:', {
      discussionId,
      content: discussionReplyContent
    });

    setReplyingToDiscussion(null);
    setDiscussionReplyContent('');
  };

  // 新增：点赞讨论
  const toggleLikeDiscussion = (discussionId: number) => {
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

    // 预留后端接口
    console.log('点赞讨论API调用:', { discussionId });
  };

  // 新增：发布新讨论
  const handlePublishDiscussion = () => {
    if (!newDiscussionForm.title.trim() || !newDiscussionForm.content.trim()) {
      alert('请填写完整的讨论标题和内容');
      return;
    }

    const newDiscussion = {
      id: Date.now(),
      student: '我',
      title: newDiscussionForm.title,
      content: newDiscussionForm.content,
      replies: [],
      likes: 0,
      time: '刚刚',
      liked: false
    };

    setDiscussions([newDiscussion, ...discussions]);

    // 预留后端接口
    console.log('发布新讨论API调用:', {
      title: newDiscussionForm.title,
      content: newDiscussionForm.content
    });

    alert('讨论发布成功！');
    setShowNewDiscussionModal(false);
    setNewDiscussionForm({ title: '', content: '' });
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
  const handleAIToTeacherRequest = () => {
    if (!aiToTeacherForm.title.trim() || !aiToTeacherForm.content.trim() || !aiToTeacherForm.reason.trim()) {
      alert('请填写完整的申请信息');
      return;
    }

    // 预留后端接口
    console.log('AI转人工申请API调用:', {
      title: aiToTeacherForm.title,
      content: aiToTeacherForm.content,
      aiAnswer: aiToTeacherForm.aiAnswer,
      reason: aiToTeacherForm.reason
    });

    alert('申请已提交！教师将尽快为您解答。');
    setShowAIToTeacherModal(false);
    setAiToTeacherForm({ title: '', content: '', aiAnswer: '', reason: '' });
  };

  // 新增：开始今日复习
  const handleStartTodayReview = () => {
    // 获取所有需要今日复习的卡组
    const todayDecks = decks.filter(d => d.nextReview === '今天');
    if (todayDecks.length === 0) {
      alert('今天没有需要复习的卡片！');
      return;
    }
    
    // 选择第一个需要复习的卡组
    setCurrentDeck(todayDecks[0]);
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
    setShowReviewModal(true);
    
    // 预留后端接口：获取今日复习卡片
    console.log('获取今日复习卡片API调用:', { courseId: id });
  };

  // 新增：开始学习卡组
  const handleStartStudy = (deck: any) => {
    setCurrentDeck(deck);
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
    setShowStudyModal(true);
    
    // 预留后端接口：开始学习卡组
    console.log('开始学习卡组API调用:', { deckId: deck.id });
  };

  // 新增：翻转卡片
  const handleFlipCard = () => {
    setIsCardFlipped(!isCardFlipped);
  };

  // 新增：回答卡片（SRS算法）
  const handleAnswerCard = (difficulty: 'forget' | 'hard' | 'good' | 'easy') => {
    // 预留后端接口：提交卡片回答
    console.log('提交卡片回答API调用:', {
      deckId: currentDeck.id,
      cardIndex: currentCardIndex,
      difficulty
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
    }
  };

  // 新增：创建卡组
  const handleCreateDeck = () => {
    if (!newDeckForm.name.trim()) {
      alert('请输入卡组名称');
      return;
    }

    const validCards = newDeckForm.cards.filter(c => c.front.trim() && c.back.trim());
    if (validCards.length === 0) {
      alert('请至少添加一张有效的卡片');
      return;
    }

    const newDeck = {
      id: Date.now(),
      name: newDeckForm.name,
      cards: validCards.length,
      mastered: 0,
      learning: 0,
      new: validCards.length,
      nextReview: '今天',
      cardList: validCards
    };

    setDecks([newDeck, ...decks]);

    // 预留后端接口：创建卡组
    console.log('创建卡组API调用:', newDeck);

    alert('卡组创建成功！');
    setShowCreateDeckModal(false);
    setNewDeckForm({ name: '', cards: [{ front: '', back: '' }] });
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

  // 新增：生成周报
  const handleGenerateWeeklyReport = () => {
    setShowWeeklyReportModal(true);
    
    // 预留后端接口：生成周报
    console.log('生成周报API调用:', { courseId: id, type: 'weekly' });
  };

  // 新增：生成月报
  const handleGenerateMonthlyReport = () => {
    setShowMonthlyReportModal(true);
    
    // 预留后端接口：生成月报
    console.log('生成月报API调用:', { courseId: id, type: 'monthly' });
  };

  // 新增：导出数据
  const handleExportData = () => {
    setShowExportDataModal(true);
  };

  // 新增：确认导出
  const handleConfirmExport = () => {
    const selectedFields = Object.entries(exportFields)
      .filter(([_, selected]) => selected)
      .map(([field]) => field);

    if (selectedFields.length === 0) {
      alert('请至少选择一个导出字段');
      return;
    }

    // 预留后端接口：导出数据
    console.log('导出数据API调用:', {
      courseId: id,
      format: exportFormat,
      fields: selectedFields
    });

    alert(`正在导出${exportFormat.toUpperCase()}格式的数据...`);
    setShowExportDataModal(false);
  };

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
                <div className="text-xs text-gray-500">{course.teacher} · {course.code}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">李</div>
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
        {activeSection === 'home' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <h1 className="text-xl font-bold text-gray-900">班级首页</h1>

            {/* 个人进度环 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <div className="flex items-center gap-6">
                <div className="relative w-32 h-32">
                  <svg className="w-full h-full transform -rotate-90">
                    <circle cx="64" cy="64" r="56" fill="none" stroke="#e5e7eb" strokeWidth="8" />
                    <circle cx="64" cy="64" r="56" fill="none" stroke="#14b8a6" strokeWidth="8" strokeDasharray="351.86" strokeDashoffset="87.97" strokeLinecap="round" />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <div className="text-2xl font-bold text-gray-900">75%</div>
                    <div className="text-xs text-gray-500">总体进度</div>
                  </div>
                </div>
                <div className="flex-1 grid grid-cols-3 gap-4">
                  <div className="text-center p-3 rounded-lg bg-blue-50">
                    <div className="text-xl font-bold text-blue-600">12/15</div>
                    <div className="text-xs text-gray-600 mt-1">已完成作业</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-green-50">
                    <div className="text-xl font-bold text-green-600">28/32</div>
                    <div className="text-xs text-gray-600 mt-1">已学章节</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-purple-50">
                    <div className="text-xl font-bold text-purple-600">47</div>
                    <div className="text-xs text-gray-600 mt-1">AI提问次数</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-5">
              {/* 课程公告 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">课程公告</h2>
                <div className="space-y-3">
                  {[
                    { title: '期中考试安排通知', time: '2小时前', important: true },
                    { title: '第6章学习资料已上传', time: '1天前', important: false },
                    { title: '本周五集中答疑', time: '2天前', important: false }
                  ].map((notice, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${notice.important ? 'bg-red-50' : 'bg-blue-50'}`}>
                        <i className={`text-base ${notice.important ? 'ri-error-warning-line text-red-600' : 'ri-notification-3-line text-blue-600'}`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{notice.title}</div>
                        <div className="text-xs text-gray-500 mt-1">{notice.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 最近更新 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">最近更新</h2>
                <div className="space-y-3">
                  {[
                    { type: 'material', title: '第6章应用层.pdf', time: '2小时前' },
                    { type: 'homework', title: '第5章课后作业', time: '1天前' },
                    { type: 'video', title: 'TCP拥塞控制讲解视频', time: '2天前' }
                  ].map((update, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                        update.type === 'material' ? 'bg-green-50' :
                        update.type === 'homework' ? 'bg-orange-50' :
                        'bg-purple-50'
                      }`}>
                        <i className={`text-base ${
                          update.type === 'material' ? 'ri-file-text-line text-green-600' :
                          update.type === 'homework' ? 'ri-file-list-3-line text-orange-600' :
                          'ri-video-line text-purple-600'
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{update.title}</div>
                        <div className="text-xs text-gray-500 mt-1">{update.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 同班学习动态 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <h2 className="text-base font-semibold text-gray-900 mb-4">同班学习动态</h2>
              <div className="space-y-3">
                {[
                  { name: '张同学', action: '完成了第5章作业', time: '10分钟前' },
                  { name: '王同学', action: '获得满分成就', time: '1小时前' },
                  { name: '李同学', action: '提出了新问题', time: '2小时前' },
                  { name: '刘同学', action: '完成了今日复习', time: '3小时前' }
                ].map((activity, index) => (
                  <div key={index} className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-400 to-blue-500 flex items-center justify-center text-white text-xs font-medium flex-shrink-0">
                      {activity.name[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-900">
                        <span className="font-medium">{activity.name}</span> {activity.action}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{activity.time}</div>
                    </div>
                  </div>
                ))}
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

            {/* 资料列表 */}
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="divide-y divide-gray-100">
                {[
                  { id: 'chapter-1-intro', name: '第1章 计算机网络概述.pdf', type: 'pdf', size: '2.3 MB', date: '2024-01-15', views: 156 },
                  { id: 'chapter-2-physical', name: '第2章 物理层.pptx', type: 'ppt', size: '5.8 MB', date: '2024-01-22', views: 142 },
                  { id: 'chapter-3-datalink', name: '第3章 数据链路层.pdf', type: 'pdf', size: '3.1 MB', date: '2024-02-12', views: 134 },
                  { id: 'chapter-4-network', name: '第4章 网络层.pptx', type: 'ppt', size: '6.5 MB', date: '2024-02-28', views: 167 },
                  { id: 'chapter-5-tcp-congestion', name: '第5章 传输层-TCP拥塞控制.pdf', type: 'pdf', size: '4.2 MB', date: '2024-03-05', views: 189 },
                  { id: 'tcp-video', name: 'TCP三次握手讲解.mp4', type: 'video', size: '45.2 MB', date: '2024-02-05', views: 189 },
                  { id: 'network-code', name: '网络层协议分析代码.zip', type: 'code', size: '1.2 MB', date: '2024-02-20', views: 98 }
                ].map((file, index) => (
                  <div 
                    key={index} 
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
                      <div className="text-sm font-medium text-gray-900">{file.name}</div>
                      <div className="text-xs text-gray-500 mt-1">{file.size} · {file.date} · {file.views}次观看</div>
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
                      <div className="text-xs text-gray-500 mt-1">
                        截止时间: {homework.deadline}
                        {homework.score !== null && ` · 得分: ${homework.score}分`}
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

        {activeSection === 'ai' && <AIAssistant />}

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
                  <div className="text-3xl font-bold">12</div>
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

        {activeSection === 'mylearning' && (
          <div className="max-w-6xl mx-auto space-y-5">
            <h1 className="text-xl font-bold text-gray-900">我的学习</h1>

            <div className="grid grid-cols-3 gap-5">
              {/* 能力雷达图 */}
              <div className="col-span-2 bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">个人能力雷达图</h2>
                <div className="flex items-center justify-center py-8">
                  <div className="relative w-80 h-80">
                    <svg viewBox="0 0 200 200" className="w-full h-full">
                      <polygon points="100,20 170,60 170,140 100,180 30,140 30,60" fill="#f0fdfa" stroke="#14b8a6" strokeWidth="1" opacity="0.3"/>
                      <polygon points="100,50 145,75 145,125 100,150 55,125 55,75" fill="#14b8a6" opacity="0.5"/>
                      <line x1="100" y1="100" x2="100" y2="20" stroke="#e5e7eb" strokeWidth="1"/>
                      <line x1="100" y1="100" x2="170" y2="60" stroke="#e5e7eb" strokeWidth="1"/>
                      <line x1="100" y1="100" x2="170" y2="140" stroke="#e5e7eb" strokeWidth="1"/>
                      <line x1="100" y1="100" x2="100" y2="180" stroke="#e5e7eb" strokeWidth="1"/>
                      <line x1="100" y1="100" x2="30" y2="140" stroke="#e5e7eb" strokeWidth="1"/>
                      <line x1="100" y1="100" x2="30" y2="60" stroke="#e5e7eb" strokeWidth="1"/>
                      <text x="100" y="15" textAnchor="middle" className="text-xs fill-gray-600">物理层</text>
                      <text x="175" y="65" textAnchor="start" className="text-xs fill-gray-600">数据链路层</text>
                      <text x="175" y="145" textAnchor="start" className="text-xs fill-gray-600">网络层</text>
                      <text x="100" y="195" textAnchor="middle" className="text-xs fill-gray-600">传输层</text>
                      <text x="20" y="145" textAnchor="end" className="text-xs fill-gray-600">应用层</text>
                      <text x="20" y="65" textAnchor="end" className="text-xs fill-gray-600">协议分析</text>
                    </svg>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-3 rounded-lg bg-teal-50">
                    <div className="text-lg font-bold text-teal-600">85</div>
                    <div className="text-xs text-gray-600 mt-1">物理层</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-blue-50">
                    <div className="text-lg font-bold text-blue-600">78</div>
                    <div className="text-xs text-gray-600 mt-1">数据链路层</div>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-green-50">
                    <div className="text-lg font-bold text-green-600">72</div>
                    <div className="text-xs text-gray-600 mt-1">网络层</div>
                  </div>
                </div>
              </div>

              {/* 学习统计 */}
              <div className="space-y-5">
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">本周统计</h2>
                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">学习时长</span>
                        <span className="text-sm font-semibold text-gray-900">18.5h</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-teal-500 rounded-full" style={{ width: '74%' }}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">作业完成</span>
                        <span className="text-sm font-semibold text-gray-900">92%</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full" style={{ width: '92%' }}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">AI提问</span>
                        <span className="text-sm font-semibold text-gray-900">47次</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: '65%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">学习报告</h2>
                  <div className="space-y-2">
                    <button 
                      onClick={handleGenerateWeeklyReport}
                      className="w-full px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-file-text-line mr-2"></i>生成周报
                    </button>
                    <button 
                      onClick={handleGenerateMonthlyReport}
                      className="w-full px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-file-chart-line mr-2"></i>生成月报
                    </button>
                    <button 
                      onClick={handleExportData}
                      className="w-full px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                    >
                      <i className="ri-download-line mr-2"></i>导出数据
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* 学习日历热力图 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <h2 className="text-base font-semibold text-gray-900 mb-4">学习日历</h2>
              <div className="space-y-2">
                {[0, 1, 2, 3, 4, 5, 6].map((week) => (
                  <div key={week} className="flex items-center gap-1">
                    {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30].map((day) => {
                      const intensity = Math.floor(Math.random() * 5);
                      return (
                        <div key={day} className={`w-3 h-3 rounded-sm cursor-pointer ${
                          intensity === 0 ? 'bg-gray-100' :
                          intensity === 1 ? 'bg-teal-100' :
                          intensity === 2 ? 'bg-teal-200' :
                          intensity === 3 ? 'bg-teal-400' :
                          'bg-teal-600'
                        }`} title={`${intensity}小时`}></div>
                      );
                    })}
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between mt-4 text-xs text-gray-500">
                <span>最近7个月学习活跃度</span>
                <div className="flex items-center gap-2">
                  <span>少</span>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 rounded-sm bg-gray-100"></div>
                    <div className="w-3 h-3 rounded-sm bg-teal-100"></div>
                    <div className="w-3 h-3 rounded-sm bg-teal-200"></div>
                    <div className="w-3 h-3 rounded-sm bg-teal-400"></div>
                    <div className="w-3 h-3 rounded-sm bg-teal-600"></div>
                  </div>
                  <span>多</span>
                </div>
              </div>
            </div>

            {/* 提问关键词云 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <h2 className="text-base font-semibold text-gray-900 mb-4">提问历史关键词</h2>
              <div className="flex flex-wrap gap-2">
                {[
                  { word: 'TCP', size: 'text-2xl', color: 'text-teal-600' },
                  { word: '三次握手', size: 'text-xl', color: 'text-blue-600' },
                  { word: '拥塞控制', size: 'text-lg', color: 'text-green-600' },
                  { word: '路由算法', size: 'text-base', color: 'text-purple-600' },
                  { word: 'IP地址', size: 'text-xl', color: 'text-orange-600' },
                  { word: '子网划分', size: 'text-base', color: 'text-pink-600' },
                  { word: 'UDP', size: 'text-lg', color: 'text-indigo-600' },
                  { word: 'HTTP', size: 'text-base', color: 'text-red-600' },
                  { word: 'DNS', size: 'text-lg', color: 'text-yellow-600' },
                  { word: '滑动窗口', size: 'text-base', color: 'text-cyan-600' },
                  { word: 'ARP', size: 'text-sm', color: 'text-gray-600' },
                  { word: 'ICMP', size: 'text-sm', color: 'text-gray-600' }
                ].map((keyword, index) => (
                  <span key={index} className={`${keyword.size} ${keyword.color} font-medium cursor-pointer hover:opacity-70`}>
                    {keyword.word}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 预览文件弹窗 */}
        {showPreviewModal && currentFile && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">预览 - {currentFile.name}</h2>
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
                    onClick={() => setShowPreviewModal(false)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                {currentFile.type === 'video' ? (
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
                      <div className="text-sm">{currentFile.type === 'pdf' ? 'PDF' : currentFile.type === 'ppt' ? 'PPT' : '代码'}文档预览</div>
                      <div className="text-xs text-gray-400 mt-2">第 1 / 25 页</div>
                    </div>
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
                    onClick={() => setShowPreviewModal(false)}
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
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">内容摘要</div>
                    <div className="text-sm text-gray-700 leading-relaxed">
                      本章节主要介绍了计算机网络的基本概念、发展历史和体系结构。重点讲解了OSI七层模型和TCP/IP四层模型的区别与联系，以及各层的主要功能和协议。通过学习本章，学生将掌握网络分层的思想和各层协议的基本原理。
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">核心知识点</div>
                    <div className="space-y-2">
                      {[
                        '计算机网络的定义与分类',
                        'OSI七层模型详解',
                        'TCP/IP协议栈结构',
                        '网络拓扑结构类型',
                        '数据传输方式（单播/广播/组播）',
                        '网络性能指标（带宽/时延/吞吐量）'
                      ].map((point, i) => (
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
                      {[
                        { title: 'OSI与TCP/IP模型对比', difficulty: '中等', desc: '需要理解两种模型的层次划分差异' },
                        { title: '各层协议的封装与解封装', difficulty: '较难', desc: '涉及数据包在各层的处理过程' },
                        { title: '网络性能指标计算', difficulty: '中等', desc: '需要掌握带宽、时延等参数的计算方法' }
                      ].map((item, i) => (
                        <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">{item.title}</span>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              item.difficulty === '较难' ? 'bg-orange-100 text-orange-600' : 'bg-yellow-100 text-yellow-600'
                            }`}>{item.difficulty}</span>
                          </div>
                          <div className="text-xs text-gray-600">{item.desc}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-semibold text-gray-900 mb-2">学习建议</div>
                    <div className="text-sm text-gray-700 leading-relaxed space-y-2">
                      <p>• 建议学习时长：2-3小时</p>
                      <p>• 配合视频讲解效果更佳</p>
                      <p>• 重点掌握OSI七层模型和TCP/IP四层模型的对应关系</p>
                      <p>• 建议完成课后习题巩固知识点</p>
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
                  onClick={() => setShowAIAnalysisModal(false)}
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
            <div className="bg-white rounded-xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">知识图谱可视化</h2>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={resetGraph}
                    className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 rounded-md hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-refresh-line mr-1"></i>重置
                  </button>
                  <button 
                    onClick={toggleGraphFullscreen}
                    className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 rounded-md hover:bg-gray-100 cursor-pointer whitespace-nowrap"
                  >
                    <i className={`${isGraphFullscreen ? 'ri-fullscreen-exit-line' : 'ri-fullscreen-line'} mr-1`}></i>
                    {isGraphFullscreen ? '退出全屏' : '全屏'}
                  </button>
                  <button
                    onClick={() => setShowKnowledgeGraphModal(false)}
                    className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    <i className="ri-close-line text-xl"></i>
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-hidden p-6" ref={graphContainerRef}>
                <div className={`${isGraphFullscreen ? 'h-screen' : 'h-[600px]'} bg-gray-50 rounded-lg overflow-hidden relative`}>
                  <svg className="w-full h-full" viewBox="0 0 1000 300">
                    {/* 绘制连线 */}
                    {getVisibleGraphNodes().map(node => {
                      if (node.parent) {
                        const parentNode = graphNodes.find(n => n.id === node.parent);
                        if (parentNode && expandedGraphNodes.includes(node.parent)) {
                          return (
                            <line
                              key={`line-${node.id}`}
                              x1={parentNode.x}
                              y1={parentNode.y}
                              x2={node.x}
                              y2={node.y}
                              stroke="#d1d5db"
                              strokeWidth="2"
                            />
                          );
                        }
                      }
                      return null;
                    })}
                    
                    {/* 绘制节点 */}
                    {getVisibleGraphNodes().map(node => {
                      const hasChildren = graphNodes.some(n => n.parent === node.id);
                      const isExpanded = expandedGraphNodes.includes(node.id);
                      
                      return (
                        <g key={node.id}>
                          <circle
                            cx={node.x}
                            cy={node.y}
                            r="30"
                            fill={node.color}
                            className="cursor-pointer transition-all hover:opacity-80"
                            onClick={() => hasChildren && toggleGraphNode(node.id)}
                          />
                          {hasChildren && (
                            <circle
                              cx={node.x}
                              cy={node.y}
                              r="12"
                              fill="white"
                              className="cursor-pointer"
                              onClick={() => toggleGraphNode(node.id)}
                            />
                          )}
                          {hasChildren && (
                            <text
                              x={node.x}
                              y={node.y + 5}
                              textAnchor="middle"
                              className="text-xs font-bold cursor-pointer select-none"
                              fill={node.color}
                              onClick={() => toggleGraphNode(node.id)}
                            >
                              {isExpanded ? '−' : '+'}
                            </text>
                          )}
                          <text
                            x={node.x}
                            y={node.y + 50}
                            textAnchor="middle"
                            className="text-xs font-medium fill-gray-700 select-none"
                          >
                            {node.label}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                  
                  {/* 图例 */}
                  <div className="absolute bottom-4 left-4 bg-white rounded-lg p-3 shadow-md border border-gray-200">
                    <div className="text-xs font-semibold text-gray-900 mb-2">图例</div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full bg-teal-500"></div>
                        <span className="text-xs text-gray-600">主节点</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full bg-blue-500"></div>
                        <span className="text-xs text-gray-600">子节点</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded-full bg-white border-2 border-gray-300 flex items-center justify-center">
                          <span className="text-xs font-bold text-gray-600">+</span>
                        </div>
                        <span className="text-xs text-gray-600">可展开</span>
                      </div>
                    </div>
                  </div>

                  {/* 操作提示 */}
                  <div className="absolute top-4 left-4 bg-white rounded-lg p-3 shadow-md border border-gray-200">
                    <div className="text-xs text-gray-600">
                      <div className="flex items-center gap-2 mb-1">
                        <i className="ri-information-line text-teal-500"></i>
                        <span className="font-semibold">操作提示</span>
                      </div>
                      <div>• 点击带 + 号的节点展开子节点</div>
                      <div>• 点击带 − 号的节点收起子节点</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 开始作业弹窗 */}
        {showHomeworkModal && currentHomework && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">{currentHomework.title}</h2>
                <button
                  onClick={() => {
                    setShowHomeworkModal(false);
                    setCurrentHomework(null);
                    setHomeworkAnswers({});
                  }}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
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
                  已完成 {Object.keys(homeworkAnswers).length} / {currentHomework.questions.length} 题
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      setShowHomeworkModal(false);
                      setCurrentHomework(null);
                      setHomeworkAnswers({});
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    暂存草稿
                  </button>
                  <button
                    onClick={handleSubmitHomework}
                    className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    提交作业
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
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
                <button
                  onClick={() => {
                    handlePracticeMistake(currentMistake);
                    setShowMistakeDetailModal(false);
                    setCurrentMistake(null);
                  }}
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
                    setNewMistakeForm({
                      question: '',
                      chapter: '',
                      myAnswer: '',
                      correctAnswer: '',
                      analysis: ''
                    });
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
                    setNewQuestionForm({ title: '', content: '', attachments: [] });
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
                    setNewDiscussionForm({ title: '', content: '' });
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
                    setAiToTeacherForm({ title: '', content: '', aiAnswer: '', reason: '' });
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
                    setNewDeckForm({ name: '', cards: [{ front: '', back: '' }] });
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

        {/* 生成周报弹窗 */}
        {showWeeklyReportModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">学习周报</h2>
                <button
                  onClick={() => setShowWeeklyReportModal(false)}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {/* 报告头部 */}
                  <div className="text-center pb-6 border-b border-gray-200">
                    <h3 className="text-2xl font-bold text-gray-900 mb-2">计算机网络 - 学习周报</h3>
                    <div className="text-sm text-gray-600">2024年3月11日 - 2024年3月17日</div>
                  </div>

                  {/* 总体概览 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">总体概览</h4>
                    <div className="grid grid-cols-4 gap-4">
                      <div className="p-4 bg-teal-50 rounded-lg border border-teal-100">
                        <div className="text-2xl font-bold text-teal-600 mb-1">18.5h</div>
                        <div className="text-xs text-gray-600">学习时长</div>
                      </div>
                      <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                        <div className="text-2xl font-bold text-green-600 mb-1">92%</div>
                        <div className="text-xs text-gray-600">作业完成率</div>
                      </div>
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div className="text-2xl font-bold text-blue-600 mb-1">47次</div>
                        <div className="text-xs text-gray-600">AI提问</div>
                      </div>
                      <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                        <div className="text-2xl font-bold text-purple-600 mb-1">156张</div>
                        <div className="text-xs text-gray-600">闪卡复习</div>
                      </div>
                    </div>
                  </div>

                  {/* 学习进度 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">学习进度</h4>
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <div className="space-y-3">
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-gray-700">第5章 传输层</span>
                            <span className="text-sm font-medium text-teal-600">100%</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full bg-teal-500 rounded-full" style={{ width: '100%' }}></div>
                          </div>
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-gray-700">第6章 应用层</span>
                            <span className="text-sm font-medium text-teal-600">65%</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full bg-teal-500 rounded-full" style={{ width: '65%' }}></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 作业完成情况 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">作业完成情况</h4>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <i className="ri-checkbox-circle-fill text-green-600 text-lg"></i>
                          <span className="text-sm text-gray-900">第5章课后作业</span>
                        </div>
                        <span className="text-sm font-medium text-green-600">88分</span>
                      </div>
                      <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <i className="ri-checkbox-circle-fill text-green-600 text-lg"></i>
                          <span className="text-sm text-gray-900">第4章图论算法实现</span>
                        </div>
                        <span className="text-sm font-medium text-green-600">92分</span>
                      </div>
                      <div className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <i className="ri-time-line text-orange-600 text-lg"></i>
                          <span className="text-sm text-gray-900">第6章应用层作业</span>
                        </div>
                        <span className="text-sm font-medium text-orange-600">进行中</span>
                      </div>
                    </div>
                  </div>

                  {/* 薄弱知识点 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">薄弱知识点</h4>
                    <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-100">
                      <div className="space-y-2">
                        <div className="flex items-start gap-2">
                          <i className="ri-error-warning-line text-yellow-600 text-base mt-0.5"></i>
                          <div>
                            <div className="text-sm font-medium text-gray-900">TCP拥塞控制算法</div>
                            <div className="text-xs text-gray-600 mt-1">建议：重点复习慢启动和拥塞避免的区别</div>
                          </div>
                        </div>
                        <div className="flex items-start gap-2">
                          <i className="ri-error-warning-line text-yellow-600 text-base mt-0.5"></i>
                          <div>
                            <div className="text-sm font-medium text-gray-900">子网划分计算</div>
                            <div className="text-xs text-gray-600 mt-1">建议：多做练习题，掌握CIDR表示法</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* AI建议 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">AI学习建议</h4>
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                      <div className="text-sm text-gray-700 leading-relaxed space-y-2">
                        <p>• 本周学习时长充足，保持良好的学习节奏</p>
                        <p>• 建议加强TCP拥塞控制算法的理解，可以通过动画演示加深印象</p>
                        <p>• 闪卡复习效果良好，建议继续保持每日复习习惯</p>
                        <p>• 第6章应用层内容较多，建议分模块学习，逐个击破</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    alert('周报已下载为PDF格式');
                    console.log('下载周报API调用');
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                >
                  <i className="ri-download-line mr-1"></i>下载PDF
                </button>
                <button
                  onClick={() => setShowWeeklyReportModal(false)}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 生成月报弹窗 */}
        {showMonthlyReportModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">学习月报</h2>
                <button
                  onClick={() => setShowMonthlyReportModal(false)}
                  className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className="ri-close-line text-xl"></i>
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-6">
                  {/* 报告头部 */}
                  <div className="text-center pb-6 border-b border-gray-200">
                    <h3 className="text-2xl font-bold text-gray-900 mb-2">计算机网络 - 学习月报</h3>
                    <div className="text-sm text-gray-600">2024年3月</div>
                  </div>

                  {/* 月度总结 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">月度总结</h4>
                    <div className="grid grid-cols-4 gap-4">
                      <div className="p-4 bg-teal-50 rounded-lg border border-teal-100">
                        <div className="text-2xl font-bold text-teal-600 mb-1">76.5h</div>
                        <div className="text-xs text-gray-600">总学习时长</div>
                      </div>
                      <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                        <div className="text-2xl font-bold text-green-600 mb-1">15/16</div>
                        <div className="text-xs text-gray-600">作业完成</div>
                      </div>
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div className="text-2xl font-bold text-blue-600 mb-1">189次</div>
                        <div className="text-xs text-gray-600">AI提问</div>
                      </div>
                      <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                        <div className="text-2xl font-bold text-purple-600 mb-1">628张</div>
                        <div className="text-xs text-gray-600">闪卡复习</div>
                      </div>
                    </div>
                  </div>

                  {/* 学习趋势 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">学习时长趋势</h4>
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-end justify-between h-40 gap-2">
                        {[12, 15, 18, 14, 20, 16, 19, 22, 18, 21, 17, 19, 23, 20, 18, 16, 19, 21, 18, 20, 17, 19, 22, 18, 20, 16, 18, 19, 17, 15].map((hours, i) => (
                          <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div 
                              className="w-full bg-teal-500 rounded-t hover:bg-teal-600 cursor-pointer transition-colors"
                              style={{ height: `${(hours / 25) * 100}%` }}
                              title={`${hours}小时`}
                            ></div>
                          </div>
                        ))}
                      </div>
                      <div className="flex items-center justify-between mt-3 text-xs text-gray-500">
                        <span>3月1日</span>
                        <span>3月15日</span>
                        <span>3月30日</span>
                      </div>
                    </div>
                  </div>

                  {/* 成绩分析 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">成绩分析</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <div className="text-sm text-gray-600 mb-2">平均分</div>
                        <div className="text-3xl font-bold text-gray-900">89.5</div>
                        <div className="text-xs text-green-600 mt-1">
                          <i className="ri-arrow-up-line"></i>较上月提升 5.2分
                        </div>
                      </div>
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <div className="text-sm text-gray-600 mb-2">班级排名</div>
                        <div className="text-3xl font-bold text-gray-900">8/45</div>
                        <div className="text-xs text-green-600 mt-1">
                          <i className="ri-arrow-up-line"></i>较上月提升 3名
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 知识掌握情况 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">知识掌握情况</h4>
                    <div className="space-y-3">
                      {[
                        { chapter: '第1章 计算机网络概述', progress: 100, color: 'green' },
                        { chapter: '第2章 物理层', progress: 100, color: 'green' },
                        { chapter: '第3章 数据链路层', progress: 95, color: 'green' },
                        { chapter: '第4章 网络层', progress: 88, color: 'teal' },
                        { chapter: '第5章 传输层', progress: 82, color: 'teal' },
                        { chapter: '第6章 应用层', progress: 65, color: 'orange' }
                      ].map((item, i) => (
                        <div key={i}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm text-gray-700">{item.chapter}</span>
                            <span className={`text-sm font-medium text-${item.color}-600`}>{item.progress}%</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div 
                              className={`h-full bg-${item.color}-500 rounded-full`}
                              style={{ width: `${item.progress}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 月度亮点 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">月度亮点</h4>
                    <div className="space-y-2">
                      <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
                        <i className="ri-trophy-line text-green-600 text-lg mt-0.5"></i>
                        <div>
                          <div className="text-sm font-medium text-gray-900">获得"学习达人"徽章</div>
                          <div className="text-xs text-gray-600 mt-1">连续30天保持学习记录</div>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                        <i className="ri-star-line text-blue-600 text-lg mt-0.5"></i>
                        <div>
                          <div className="text-sm font-medium text-gray-900">第5章作业获得满分</div>
                          <div className="text-xs text-gray-600 mt-1">教师评价：理解深刻，代码规范</div>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
                        <i className="ri-lightbulb-line text-purple-600 text-lg mt-0.5"></i>
                        <div>
                          <div className="text-sm font-medium text-gray-900">提出高质量问题3次</div>
                          <div className="text-xs text-gray-600 mt-1">获得教师和同学点赞</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 下月建议 */}
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-3">下月学习建议</h4>
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                      <div className="text-sm text-gray-700 leading-relaxed space-y-2">
                        <p>• 继续保持良好的学习习惯，每日学习时长稳定在2-3小时</p>
                        <p>• 重点攻克第6章应用层内容，建议分HTTP、DNS、FTP等模块逐个学习</p>
                        <p>• 加强编程实践，多做网络协议分析实验</p>
                        <p>• 准备期中考试，系统复习前5章内容</p>
                        <p>• 建议参加班级讨论，与同学交流学习心得</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => {
                    alert('月报已下载为PDF格式');
                    console.log('下载月报API调用');
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap"
                >
                  <i className="ri-download-line mr-1"></i>下载PDF
                </button>
                <button
                  onClick={() => setShowMonthlyReportModal(false)}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 导出数据弹窗 */}
        {showExportDataModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl w-full max-w-lg overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                <h2 className="text-lg font-semibold text-gray-900">导出学习数据</h2>
              </div>
              
              <div className="p-6">
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-3">导出格式</label>
                    <div className="flex gap-3">
                      <label className="flex-1 flex items-center gap-3 p-3 border-2 rounded-lg cursor-pointer transition-colors hover:border-teal-300">
                        <input
                          type="radio"
                          name="format"
                          value="csv"
                          checked={exportFormat === 'csv'}
                          onChange={(e) => setExportFormat(e.target.value)}
                          className="w-4 h-4 accent-teal-600"
                        />
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900">CSV</div>
                          <div className="text-xs text-gray-500">适合Excel打开</div>
                        </div>
                      </label>
                      <label className="flex-1 flex items-center gap-3 p-3 border-2 rounded-lg cursor-pointer transition-colors hover:border-teal-300">
                        <input
                          type="radio"
                          name="format"
                          value="excel"
                          checked={exportFormat === 'excel'}
                          onChange={(e) => setExportFormat(e.target.value)}
                          className="w-4 h-4 accent-teal-600"
                        />
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900">Excel</div>
                          <div className="text-xs text-gray-500">包含格式和图表</div>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-3">选择导出字段</label>
                    <div className="space-y-2">
                      {[
                        { key: 'studyTime', label: '学习时长记录' },
                        { key: 'homework', label: '作业完成情况' },
                        { key: 'aiQuestions', label: 'AI提问历史' },
                        { key: 'attendance', label: '出勤记录' },
                        { key: 'grades', label: '成绩记录' }
                      ].map((field) => (
                        <label key={field.key} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100">
                          <input
                            type="checkbox"
                            checked={exportFields[field.key as keyof typeof exportFields]}
                            onChange={(e) => setExportFields({ ...exportFields, [field.key]: e.target.checked })}
                            className="w-4 h-4 accent-teal-600"
                          />
                          <span className="text-sm text-gray-900">{field.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  onClick={() => setShowExportDataModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmExport}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  确认导出
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}