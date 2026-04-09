import { useState, useRef, useEffect, useCallback } from 'react';

interface FeedbackItem {
  id: string;
  studentName: string;
  conversationTitle: string;
  questionContent: string;
  aiAnswer: string;
  reason: string;
  timestamp: string;
  status: 'pending' | 'resolved';
  courseId?: string;
}

interface AttachedFile {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  fileType: 'image' | 'pdf' | 'docx' | 'md' | 'code' | 'other';
  preview?: string;
}

interface Message {
  id: number;
  role: 'user' | 'ai';
  content: string;
  time: string;
  attachments?: AttachedFile[];
  sources?: { name: string; page: number; type: string }[];
  isWelcome?: boolean;
}

interface Conversation {
  id: number;
  title: string;
  createdAt: string;
  lastMessage: string;
  messages: Message[];
}

interface TeacherRecommendation {
  id: number;
  title: string;
  type: 'report' | 'template' | 'insight' | 'alert';
  desc: string;
  icon: string;
  iconColor: string;
  iconBg: string;
}

const AI_RESPONSES: Record<string, { content: string; sources?: { name: string; page: number; type: string }[] }> = {
  default: {
    content: '根据课程数据分析，我来为您提供相关教学建议。\n\n当前班级整体学习状况良好，平均进度达到了75%。建议关注学习进度落后的学生，及时给予个性化辅导。',
    sources: [{ name: '班级学情报告.pdf', page: 1, type: 'pdf' }],
  },
  file: {
    content: '已收到您上传的文件，正在解析内容...\n\n**文件解析完成**，主要内容如下：\n\n• 文件已关联到课程知识库，可用于生成教案和试卷\n• 识别到相关知识点，已建立知识关联\n• 建议将此文件作为参考资料分发给学生\n\n需要我基于此文件生成教案或习题吗？',
    sources: [{ name: '上传文件', page: 1, type: 'pdf' }],
  },
  tcp: {
    content: 'TCP三次握手过程如下：\n\n**第一次握手**：客户端发送SYN报文（SYN=1, seq=x），进入SYN_SENT状态。\n\n**第二次握手**：服务器收到后回复SYN+ACK报文（SYN=1, ACK=1, seq=y, ack=x+1），进入SYN_RCVD状态。\n\n**第三次握手**：客户端发送ACK报文（ACK=1, seq=x+1, ack=y+1），双方进入ESTABLISHED状态。',
    sources: [{ name: '第4章-传输层.pdf', page: 12, type: 'pdf' }],
  },
  lesson: {
    content: '根据您的课程内容和学生学情，我为您生成以下教案大纲：\n\n**教学目标**\n• 理解TCP三次握手的完整过程\n• 掌握各状态的转换条件\n• 能够分析常见连接问题\n\n**教学重点难点**\n• 重点：三次握手必要性\n• 难点：第三次握手为什么必须有\n\n**教学流程**\n1. 导入：为什么需要建立连接（5min）\n2. 讲解：三次握手详细过程（20min）\n3. 演示：Wireshark抓包分析（10min）\n4. 练习：连接状态题目（15min）',
    sources: [{ name: '教学大纲.docx', page: 1, type: 'pdf' }],
  },
  analysis: {
    content: '**班级学情分析报告**\n\n**整体情况**\n本班68名学生，平均学习进度75%，整体表现良好。\n\n**薄弱环节**\n1. TCP拥塞控制：约35%的学生掌握不足\n2. 子网划分计算：约28%的学生需要加强\n3. 路由算法：约22%的学生理解不深\n\n**建议措施**\n• 增加TCP拥塞控制的习题练习\n• 设计专项子网划分练习课\n• 制作路由算法动画演示材料',
    sources: [{ name: '学情数据.xlsx', page: 0, type: 'pdf' }],
  },
};

function getAIResponse(input: string, hasFiles: boolean) {
  if (hasFiles) return AI_RESPONSES.file;
  const lower = input.toLowerCase();
  if (lower.includes('tcp') || lower.includes('握手')) return AI_RESPONSES.tcp;
  if (lower.includes('教案') || lower.includes('备课') || lower.includes('课程设计')) return AI_RESPONSES.lesson;
  if (lower.includes('学情') || lower.includes('分析') || lower.includes('统计')) return AI_RESPONSES.analysis;
  return AI_RESPONSES.default;
}

function getFileType(file: File): AttachedFile['fileType'] {
  const name = file.name.toLowerCase();
  const mime = file.type;
  if (mime.startsWith('image/')) return 'image';
  if (mime === 'application/pdf') return 'pdf';
  if (mime.includes('word') || name.endsWith('.docx') || name.endsWith('.doc')) return 'docx';
  if (name.endsWith('.md') || name.endsWith('.markdown')) return 'md';
  const codeExts = ['.py', '.js', '.ts', '.jsx', '.tsx', '.cpp', '.c', '.java', '.go', '.rs', '.html', '.css', '.json', '.yaml', '.yml', '.sh', '.php', '.rb', '.swift', '.kt'];
  if (codeExts.some(ext => name.endsWith(ext))) return 'code';
  return 'other';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function generateTitle(firstMessage: string): string {
  if (firstMessage.length <= 20) return firstMessage;
  return firstMessage.slice(0, 18) + '…';
}

const TEACHER_RECOMMENDATIONS: TeacherRecommendation[] = [
  { id: 1, title: '本周班级学情周报', type: 'report', desc: 'AI自动生成，含进度分析', icon: 'ri-bar-chart-2-line', iconColor: 'text-teal-600', iconBg: 'bg-teal-50' },
  { id: 2, title: '3名预警学生提醒', type: 'alert', desc: '学习进度落后超30%', icon: 'ri-alert-line', iconColor: 'text-orange-600', iconBg: 'bg-orange-50' },
  { id: 3, title: 'TCP章节教案模板', type: 'template', desc: '根据本章内容智能生成', icon: 'ri-file-text-line', iconColor: 'text-green-600', iconBg: 'bg-green-50' },
  { id: 4, title: '高频错题智能分析', type: 'insight', desc: '本周学生错误最多的5道题', icon: 'ri-error-warning-line', iconColor: 'text-red-500', iconBg: 'bg-red-50' },
];

const getNow = () => {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
};

const formatDate = (d: Date) => {
  const today = new Date();
  const diff = today.getDate() - d.getDate();
  if (diff === 0) return '今天';
  if (diff === 1) return '昨天';
  return `${d.getMonth() + 1}月${d.getDate()}日`;
};

const INIT_WELCOME: Message = {
  id: 1, role: 'ai',
  content: '您好！我是珞樱学堂AI助教，已加载《计算机网络》课程知识库。\n\n我可以帮您：解答课程疑问、生成教案试卷、分析学情数据。\n\n支持上传教材图片、Word文档、代码文件等，我会结合文件内容为您提供更精准的支持！',
  time: getNow(),
  isWelcome: true,
};

const fileTypeConfig: Record<AttachedFile['fileType'], { icon: string; color: string; bg: string; label: string }> = {
  image: { icon: 'ri-image-line', color: 'text-green-600', bg: 'bg-green-50', label: '图片' },
  pdf: { icon: 'ri-file-pdf-line', color: 'text-red-500', bg: 'bg-red-50', label: 'PDF' },
  docx: { icon: 'ri-file-word-line', color: 'text-sky-600', bg: 'bg-sky-50', label: 'Word' },
  md: { icon: 'ri-markdown-line', color: 'text-gray-600', bg: 'bg-gray-100', label: 'Markdown' },
  code: { icon: 'ri-code-s-slash-line', color: 'text-teal-600', bg: 'bg-teal-50', label: '代码' },
  other: { icon: 'ri-file-line', color: 'text-gray-500', bg: 'bg-gray-50', label: '文件' },
};

function loadFeedbacks(): FeedbackItem[] {
  try {
    return JSON.parse(localStorage.getItem('luoying_ai_feedback') || '[]');
  } catch {
    return [];
  }
}

function FeedbackDetailModal({ item, onClose, onResolve }: {
  item: FeedbackItem;
  onClose: () => void;
  onResolve: (id: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose}></div>
      <div className="relative bg-white rounded-2xl shadow-xl w-[520px] max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 flex items-center justify-center rounded-full bg-orange-50">
              <i className="ri-thumb-down-fill text-orange-500"></i>
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-900">学生反馈详情</div>
              <div className="text-xs text-gray-500">{item.studentName} · {item.timestamp}</div>
            </div>
          </div>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 cursor-pointer">
            <i className="ri-close-line text-base"></i>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          <div>
            <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">对话标题</div>
            <div className="text-sm text-gray-800 px-3 py-2 bg-gray-50 rounded-lg">{item.conversationTitle}</div>
          </div>

          {item.questionContent && (
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">学生提问</div>
              <div className="text-sm text-gray-800 px-3 py-2.5 bg-teal-50 rounded-lg border border-teal-100 leading-relaxed">{item.questionContent}</div>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">AI 回答内容</div>
            <div className="text-sm text-gray-700 px-3 py-2.5 bg-gray-50 rounded-lg border border-gray-100 leading-relaxed max-h-40 overflow-y-auto whitespace-pre-wrap">{item.aiAnswer}</div>
          </div>

          {item.reason && (
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">学生反馈原因</div>
              <div className="flex items-start gap-2 px-3 py-2.5 bg-orange-50 rounded-lg border border-orange-100">
                <i className="ri-feedback-line text-orange-500 text-sm mt-0.5 flex-shrink-0"></i>
                <span className="text-sm text-orange-800">{item.reason}</span>
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between flex-shrink-0">
          <div className={`flex items-center gap-1.5 text-xs font-medium ${item.status === 'resolved' ? 'text-green-600' : 'text-orange-500'}`}>
            <i className={item.status === 'resolved' ? 'ri-checkbox-circle-fill' : 'ri-time-line'}></i>
            {item.status === 'resolved' ? '已处理' : '待处理'}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors cursor-pointer whitespace-nowrap">
              关闭
            </button>
            {item.status === 'pending' && (
              <button
                onClick={() => { onResolve(item.id); onClose(); }}
                className="px-4 py-2 text-sm font-medium text-white bg-teal-600 rounded-xl hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-check-line mr-1"></i>标记已处理
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TeacherAIAssistant() {
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: 1, title: '生成TCP章节教案',
      createdAt: formatDate(new Date(Date.now() - 86400000)),
      lastMessage: '已为您生成教案大纲，包含教学目标...',
      messages: [
        { ...INIT_WELCOME, id: 1 },
        { id: 2, role: 'user', content: '请帮我生成TCP三次握手的教案', time: '10:20' },
        { id: 3, ...AI_RESPONSES.lesson, role: 'ai', time: '10:21' },
      ],
    },
    {
      id: 2, title: '班级学情分析',
      createdAt: formatDate(new Date(Date.now() - 172800000)),
      lastMessage: '本班68名学生，平均学习进度75%...',
      messages: [
        { ...INIT_WELCOME, id: 1 },
        { id: 2, role: 'user', content: '请分析本班的学情状况', time: '15:00' },
        { id: 3, ...AI_RESPONSES.analysis, role: 'ai', time: '15:01' },
      ],
    },
  ]);

  const [activeConvId, setActiveConvId] = useState<number>(0);
  const [messages, setMessages] = useState<Message[]>([{ ...INIT_WELCOME }]);
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [knowledgeBase, setKnowledgeBase] = useState('course');
  const [style, setStyle] = useState('academic');
  const [currentSources, setCurrentSources] = useState<{ name: string; page: number; type: string }[]>([]);
  const [showConvList, setShowConvList] = useState(true);

  // Student feedback
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>(loadFeedbacks);
  const [feedbackDetailItem, setFeedbackDetailItem] = useState<FeedbackItem | null>(null);
  const [feedbackExpanded, setFeedbackExpanded] = useState(true);

  const pendingCount = feedbacks.filter(f => f.status === 'pending').length;

  // Reload feedbacks when tab becomes visible (simulate real-time)
  useEffect(() => {
    const handleVisibility = () => {
      if (!document.hidden) setFeedbacks(loadFeedbacks());
    };
    document.addEventListener('visibilitychange', handleVisibility);
    const interval = setInterval(() => setFeedbacks(loadFeedbacks()), 3000);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      clearInterval(interval);
    };
  }, []);

  const handleResolveFeedback = (id: string) => {
    const updated = feedbacks.map(f => f.id === id ? { ...f, status: 'resolved' as const } : f);
    setFeedbacks(updated);
    localStorage.setItem('luoying_ai_feedback', JSON.stringify(updated));
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const autoResizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  useEffect(() => {
    autoResizeTextarea();
  }, [input, autoResizeTextarea]);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const ALLOWED_TYPES = [
      'image/jpeg', 'image/png', 'image/gif', 'image/webp',
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
      'text/markdown', 'text/plain', 'text/html', 'text/css',
      'application/json', 'text/x-python', 'text/javascript', 'application/javascript',
    ];
    const ALLOWED_EXTS = ['.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.cpp', '.c', '.java', '.go', '.rs', '.yaml', '.yml', '.sh', '.php', '.rb', '.swift', '.kt', '.json', '.html', '.css', '.docx', '.doc'];
    const MAX_SIZE = 20 * 1024 * 1024;
    const newFiles: AttachedFile[] = [];
    for (const file of fileArray) {
      if (file.size > MAX_SIZE) continue;
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      const allowed = ALLOWED_TYPES.includes(file.type) || ALLOWED_EXTS.includes(ext);
      if (!allowed) continue;
      const fileType = getFileType(file);
      let preview: string | undefined;
      if (fileType === 'image') {
        preview = await new Promise<string>(resolve => {
          const reader = new FileReader();
          reader.onload = e => resolve(e.target?.result as string);
          reader.readAsDataURL(file);
        });
      }
      newFiles.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        name: file.name, size: file.size, mimeType: file.type, fileType, preview,
      });
    }
    if (newFiles.length > 0) setAttachedFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) processFiles(e.target.files);
    e.target.value = '';
  };
  const handleRemoveAttachment = (id: string) => setAttachedFiles(prev => prev.filter(f => f.id !== id));
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) processFiles(e.dataTransfer.files);
  };

  const handleSelectConversation = (convId: number) => {
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    setActiveConvId(convId);
    setMessages(conv.messages);
    setCurrentSources([]);
    setAttachedFiles([]);
  };

  const handleNewConversation = () => {
    setActiveConvId(0);
    setMessages([{ ...INIT_WELCOME, id: Date.now() }]);
    setInput('');
    setAttachedFiles([]);
    setCurrentSources([]);
  };

  const saveCurrentConversation = useCallback((newMessages: Message[]) => {
    if (activeConvId === 0) {
      const userMsgs = newMessages.filter(m => m.role === 'user');
      if (userMsgs.length === 0) return;
      const title = generateTitle(userMsgs[0].content || (userMsgs[0].attachments?.[0]?.name ?? '新对话'));
      const lastAI = [...newMessages].reverse().find(m => m.role === 'ai');
      const newConv: Conversation = {
        id: Date.now(), title,
        createdAt: formatDate(new Date()),
        lastMessage: lastAI ? lastAI.content.slice(0, 40) + '...' : '',
        messages: newMessages,
      };
      setConversations(prev => [newConv, ...prev]);
      setActiveConvId(newConv.id);
    } else {
      const lastAI = [...newMessages].reverse().find(m => m.role === 'ai');
      setConversations(prev =>
        prev.map(c =>
          c.id === activeConvId
            ? { ...c, messages: newMessages, lastMessage: lastAI ? lastAI.content.slice(0, 40) + '...' : c.lastMessage }
            : c
        )
      );
    }
  }, [activeConvId]);

  const sendMessage = async () => {
    const text = input.trim();
    if ((!text && attachedFiles.length === 0) || isTyping) return;
    const userMsg: Message = {
      id: Date.now(), role: 'user',
      content: text, time: getNow(),
      attachments: attachedFiles.length > 0 ? [...attachedFiles] : undefined,
    };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setAttachedFiles([]);
    setIsTyping(true);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    await new Promise(r => setTimeout(r, 1200 + Math.random() * 800));
    const resp = getAIResponse(text, (userMsg.attachments?.length ?? 0) > 0);
    const aiMsg: Message = {
      id: Date.now() + 1, role: 'ai',
      content: resp.content, time: getNow(),
      sources: resp.sources,
    };
    const finalMessages = [...nextMessages, aiMsg];
    setMessages(finalMessages);
    if (resp.sources) setCurrentSources(resp.sources);
    setIsTyping(false);
    saveCurrentConversation(finalMessages);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleDeleteConversation = (convId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (activeConvId === convId) handleNewConversation();
  };

  const renderContent = (content: string) =>
    content.split('\n').map((line, i) => {
      const bold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return <p key={i} className={line === '' ? 'mt-1' : 'leading-relaxed'} dangerouslySetInnerHTML={{ __html: bold }} />;
    });

  const quickPrompts = [
    { label: '生成教案', icon: 'ri-file-text-line', color: 'text-teal-600', prompt: '请帮我生成本章节的教案大纲' },
    { label: '生成试卷', icon: 'ri-file-list-line', color: 'text-green-600', prompt: '请帮我生成一份包含10道题的测验试卷' },
    { label: '学情分析', icon: 'ri-bar-chart-line', color: 'text-amber-600', prompt: '请分析当前班级的整体学情状况' },
    { label: '生成卡组', icon: 'ri-flashlight-line', color: 'text-orange-600', prompt: '请为本章节生成学习闪卡卡组' },
  ];

  const canSend = (input.trim() !== '' || attachedFiles.length > 0) && !isTyping;

  return (
    <div className="max-w-full">
      {/* Feedback detail modal */}
      {feedbackDetailItem && (
        <FeedbackDetailModal
          item={feedbackDetailItem}
          onClose={() => setFeedbackDetailItem(null)}
          onResolve={handleResolveFeedback}
        />
      )}

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-900">AI助教</h1>
        <button
          onClick={() => setShowConvList(v => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer whitespace-nowrap"
        >
          <i className={`${showConvList ? 'ri-layout-left-line' : 'ri-layout-right-2-line'} text-sm`}></i>
          {showConvList ? '收起对话列表' : '展开对话列表'}
        </button>
      </div>

      <div className="flex gap-3" style={{ height: 'calc(100vh - 152px)', minHeight: '560px' }}>
        {/* 左侧对话列表 */}
        {showConvList && (
          <div className="flex flex-col bg-white rounded-xl border border-gray-200" style={{ width: '220px', flexShrink: 0 }}>
            <div className="px-3 py-3 border-b border-gray-100 flex-shrink-0">
              <button
                onClick={handleNewConversation}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line text-base"></i>新建对话
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {activeConvId === 0 && (
                <div className="mx-2 mt-2 px-3 py-2.5 bg-teal-50 rounded-lg border border-teal-200">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-teal-500 flex-shrink-0"></div>
                    <span className="text-xs font-semibold text-teal-700 truncate">新对话</span>
                  </div>
                  <div className="text-xs text-teal-600 mt-0.5 truncate">正在进行中...</div>
                </div>
              )}
              {conversations.length > 0 && (
                <div className="px-2 py-2 space-y-1">
                  <div className="text-xs font-medium text-gray-400 px-2 py-1">历史对话</div>
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={`group relative px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                        activeConvId === conv.id ? 'bg-teal-50 border border-teal-200' : 'hover:bg-gray-50 border border-transparent'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-1">
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs font-medium truncate ${activeConvId === conv.id ? 'text-teal-700' : 'text-gray-800'}`}>{conv.title}</div>
                          <div className="text-xs text-gray-400 mt-0.5 truncate">{conv.createdAt}</div>
                        </div>
                        <button
                          onClick={e => handleDeleteConversation(conv.id, e)}
                          className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all flex-shrink-0"
                        >
                          <i className="ri-delete-bin-line text-xs"></i>
                        </button>
                      </div>
                      {activeConvId !== conv.id && (
                        <div className="text-xs text-gray-400 mt-0.5 truncate">{conv.lastMessage}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="px-3 py-3 border-t border-gray-100 flex-shrink-0">
              <div className="text-xs text-gray-400 text-center">{conversations.length} 段历史对话</div>
            </div>
          </div>
        )}

        {/* 主对话区 */}
        <div className="flex flex-col bg-white rounded-xl border border-gray-200 flex-1 min-w-0">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 flex items-center justify-center rounded-full bg-teal-500 text-white">
                <i className="ri-robot-line text-base"></i>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  {activeConvId === 0 ? '新对话' : conversations.find(c => c.id === activeConvId)?.title || 'AI助教'}
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
                  <span className="text-xs text-gray-500">在线</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={knowledgeBase}
                onChange={e => setKnowledgeBase(e.target.value)}
                className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-gray-50 cursor-pointer"
              >
                <option value="course">计算机网络知识库</option>
                <option value="global">全局知识库</option>
              </select>
              <button
                onClick={handleNewConversation}
                className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-teal-600 cursor-pointer rounded-md hover:bg-teal-50 transition-colors"
                title="新建对话"
              >
                <i className="ri-add-circle-line text-sm"></i>
              </button>
            </div>
          </div>

          {/* 消息列表 */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.map(msg => (
              <div key={msg.id} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 ${msg.role === 'ai' ? 'bg-teal-500' : 'bg-gray-700'}`}>
                  {msg.role === 'ai' ? <i className="ri-robot-line"></i> : <span>王</span>}
                </div>
                <div className={`max-w-[75%] flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className={`flex flex-wrap gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {msg.attachments.map(f => {
                        const cfg = fileTypeConfig[f.fileType];
                        return (
                          <div key={f.id} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs ${msg.role === 'user' ? 'bg-teal-50 border-teal-200' : 'bg-gray-50 border-gray-200'}`}>
                            {f.fileType === 'image' && f.preview ? (
                              <img src={f.preview} alt={f.name} className="w-12 h-12 object-cover rounded-lg" />
                            ) : (
                              <>
                                <div className={`w-7 h-7 flex items-center justify-center rounded-lg ${cfg.bg}`}>
                                  <i className={`${cfg.icon} ${cfg.color} text-sm`}></i>
                                </div>
                                <div>
                                  <div className="font-medium text-gray-800 max-w-[120px] truncate">{f.name}</div>
                                  <div className="text-gray-400">{formatFileSize(f.size)}</div>
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {msg.content && (
                    <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed space-y-0.5 ${msg.role === 'ai' ? 'bg-gray-50 text-gray-800 border border-gray-100' : 'bg-teal-600 text-white'}`}>
                      {renderContent(msg.content)}
                    </div>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {msg.sources.map((s, i) => (
                        <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-teal-50 border border-teal-100 rounded-full text-xs text-teal-700 cursor-pointer hover:bg-teal-100 transition-colors">
                          <i className={`text-base ${s.type === 'pdf' ? 'ri-file-pdf-line text-red-500' : s.type === 'video' ? 'ri-video-line text-purple-500' : 'ri-file-ppt-line text-orange-500'}`}></i>
                          {s.name.length > 14 ? s.name.slice(0, 14) + '…' : s.name}
                          {s.page > 0 && ` · P${s.page}`}
                        </span>
                      ))}
                    </div>
                  )}
                  <span className="text-xs text-gray-400">{msg.time}</span>
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                  <i className="ri-robot-line"></i>
                </div>
                <div className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3">
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 快捷提问 */}
          <div className="px-5 py-2 border-t border-gray-100 flex gap-2 flex-wrap flex-shrink-0">
            {['请帮我生成TCP三次握手教案', '请分析班级学情', '生成期中考试试卷'].map((q, i) => (
              <button
                key={i}
                onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                className="px-2.5 py-1 text-xs text-teal-700 bg-teal-50 border border-teal-100 rounded-full hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap"
              >
                {q}
              </button>
            ))}
          </div>

          {/* 增强输入区域 */}
          <div className="px-4 pb-4 pt-2 flex-shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh,.php,.rb,.swift,.kt"
              onChange={handleFileInputChange}
              className="hidden"
            />
            <div
              className={`rounded-xl border transition-all ${
                isDragOver
                  ? 'border-teal-400 bg-teal-50/60 ring-2 ring-teal-200'
                  : 'border-gray-200 bg-gray-50 focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {attachedFiles.length > 0 && (
                <div className="px-3 pt-3 pb-2 flex flex-wrap gap-2 border-b border-gray-200/60">
                  {attachedFiles.map(f => {
                    const cfg = fileTypeConfig[f.fileType];
                    return (
                      <div key={f.id} className="group relative flex items-center gap-1.5 pl-2 pr-1 py-1 bg-white border border-gray-200 rounded-lg text-xs max-w-[180px]">
                        {f.fileType === 'image' && f.preview ? (
                          <img src={f.preview} alt={f.name} className="w-5 h-5 object-cover rounded flex-shrink-0" />
                        ) : (
                          <div className={`w-5 h-5 flex items-center justify-center rounded flex-shrink-0 ${cfg.bg}`}>
                            <i className={`${cfg.icon} ${cfg.color} text-xs`}></i>
                          </div>
                        )}
                        <span className="text-gray-700 font-medium truncate max-w-[100px]">{f.name}</span>
                        <span className="text-gray-400 flex-shrink-0">{formatFileSize(f.size)}</span>
                        <button
                          onClick={() => handleRemoveAttachment(f.id)}
                          className="w-4 h-4 flex items-center justify-center text-gray-400 hover:text-red-500 cursor-pointer flex-shrink-0 ml-0.5"
                        >
                          <i className="ri-close-line text-xs"></i>
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="px-3 py-2.5">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isDragOver ? '松开鼠标上传文件...' : '输入问题，或拖拽文件到此处 · Enter 发送，Shift+Enter 换行'}
                  rows={1}
                  disabled={isTyping}
                  className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none resize-none leading-relaxed"
                  style={{ minHeight: '36px', maxHeight: '120px' }}
                />
              </div>
              <div className="px-3 pb-2.5 flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="上传文件"
                    className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-teal-600 hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-attachment-2 text-base"></i>
                  </button>
                  <button
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.accept = 'image/*';
                        fileInputRef.current.click();
                        setTimeout(() => { if (fileInputRef.current) fileInputRef.current.accept = 'image/*,.pdf,.doc,.docx,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh'; }, 1000);
                      }
                    }}
                    title="上传图片"
                    className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-image-add-line text-base"></i>
                  </button>
                  <button
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.accept = '.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh,.php,.rb,.swift,.kt,.md';
                        fileInputRef.current.click();
                        setTimeout(() => { if (fileInputRef.current) fileInputRef.current.accept = 'image/*,.pdf,.doc,.docx,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh'; }, 1000);
                      }
                    }}
                    title="上传代码文件"
                    className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-teal-600 hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-code-s-slash-line text-base"></i>
                  </button>
                  {attachedFiles.length > 0 && (
                    <span className="text-xs text-gray-400 ml-1">已附 {attachedFiles.length} 个文件</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 hidden sm:block">Enter发送 · Shift+Enter换行</span>
                  <button
                    onClick={sendMessage}
                    disabled={!canSend}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
                      canSend ? 'bg-teal-600 text-white hover:bg-teal-700' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    <i className="ri-send-plane-fill text-sm"></i>发送
                  </button>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-1.5 px-1">
              <i className="ri-information-line text-xs text-gray-400"></i>
              <span className="text-xs text-gray-400">支持上传：图片、PDF、Word、Markdown、代码文件（≤20MB）· 可拖拽文件到输入框</span>
            </div>
          </div>
        </div>

        {/* 右侧面板 */}
        <div className="flex flex-col gap-3 overflow-y-auto" style={{ width: '240px', flexShrink: 0 }}>
          {/* 学生反馈 - 优先展示 */}
          <div className={`bg-white rounded-xl border flex-shrink-0 ${pendingCount > 0 ? 'border-orange-200' : 'border-gray-200'}`}>
            <button
              onClick={() => setFeedbackExpanded(v => !v)}
              className="w-full px-4 py-3 flex items-center justify-between cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <i className="ri-feedback-line text-orange-500 text-sm"></i>
                <span className="text-sm font-semibold text-gray-900">学生反馈</span>
                {pendingCount > 0 && (
                  <span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 text-xs font-bold text-white bg-orange-500 rounded-full">
                    {pendingCount}
                  </span>
                )}
              </div>
              <i className={`ri-arrow-${feedbackExpanded ? 'up' : 'down'}-s-line text-gray-400 text-sm`}></i>
            </button>

            {feedbackExpanded && (
              <div className="px-3 pb-3 border-t border-gray-100">
                {feedbacks.length === 0 ? (
                  <div className="py-4 flex flex-col items-center text-gray-400">
                    <i className="ri-thumb-down-line text-2xl mb-1.5"></i>
                    <div className="text-xs text-center">暂无学生点踩反馈</div>
                  </div>
                ) : (
                  <div className="space-y-2 mt-2 max-h-52 overflow-y-auto">
                    {feedbacks.map(item => (
                      <div
                        key={item.id}
                        onClick={() => setFeedbackDetailItem(item)}
                        className={`p-2.5 rounded-lg border cursor-pointer transition-colors group ${
                          item.status === 'pending'
                            ? 'border-orange-100 bg-orange-50/60 hover:border-orange-300'
                            : 'border-gray-100 bg-gray-50 hover:border-gray-200'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5">
                            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.status === 'pending' ? 'bg-orange-500' : 'bg-gray-300'}`}></div>
                            <span className="text-xs font-medium text-gray-800">{item.studentName}</span>
                          </div>
                          <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                            item.status === 'pending' ? 'bg-orange-100 text-orange-600' : 'bg-gray-100 text-gray-500'
                          }`}>
                            {item.status === 'pending' ? '待处理' : '已处理'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 truncate">{item.conversationTitle}</div>
                        {item.reason && (
                          <div className="text-xs text-gray-400 truncate mt-0.5">{item.reason}</div>
                        )}
                        <div className="text-xs text-gray-400 mt-1">{item.timestamp.split(' ')[0]}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 便捷功能 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-shrink-0">
            <div className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <i className="ri-magic-line text-teal-500"></i>便捷功能
            </div>
            <div className="grid grid-cols-2 gap-2">
              {quickPrompts.map((item, i) => (
                <button
                  key={i}
                  onClick={() => { setInput(item.prompt); textareaRef.current?.focus(); }}
                  className="flex items-center gap-2 px-2.5 py-2 text-xs font-medium text-gray-700 bg-gray-50 rounded-lg hover:bg-teal-50 hover:text-teal-700 transition-colors cursor-pointer whitespace-nowrap border border-transparent hover:border-teal-100"
                >
                  <i className={`${item.icon} ${item.color} text-sm`}></i>
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* 对话风格 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-shrink-0">
            <div className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <i className="ri-palette-line text-teal-500"></i>对话风格
            </div>
            <div className="space-y-1.5">
              {[
                { value: 'academic', label: '严谨学术型', icon: 'ri-graduation-cap-line' },
                { value: 'inspire', label: '启发引导型', icon: 'ri-lightbulb-line' },
                { value: 'debug', label: 'Debug调试型', icon: 'ri-code-s-slash-line' },
              ].map(s => (
                <label key={s.value} className={`flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors border ${style === s.value ? 'border-teal-300 bg-teal-50' : 'border-gray-100 hover:bg-gray-50'}`}>
                  <input type="radio" name="ai-style-teacher" value={s.value} checked={style === s.value} onChange={() => setStyle(s.value)} className="w-3.5 h-3.5 accent-teal-600" />
                  <i className={`${s.icon} text-sm ${style === s.value ? 'text-teal-600' : 'text-gray-500'}`}></i>
                  <span className={`text-xs font-medium ${style === s.value ? 'text-teal-700' : 'text-gray-800'}`}>{s.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 教学智能建议 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-shrink-0">
            <div className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <i className="ri-lightbulb-flash-line text-amber-500"></i>智能建议
            </div>
            <div className="text-xs text-gray-400 mb-3">基于班级数据的教学提示</div>
            <div className="space-y-2">
              {TEACHER_RECOMMENDATIONS.map(rec => (
                <div key={rec.id} className="flex items-center gap-2.5 p-2.5 rounded-lg border border-gray-100 hover:border-teal-200 hover:bg-teal-50/40 cursor-pointer transition-colors">
                  <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${rec.iconBg}`}>
                    <i className={`${rec.icon} ${rec.iconColor} text-base`}></i>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-gray-800 truncate">{rec.title}</div>
                    <div className="text-xs text-gray-400 mt-0.5 truncate">{rec.desc}</div>
                  </div>
                  <i className="ri-arrow-right-s-line text-gray-400 flex-shrink-0"></i>
                </div>
              ))}
            </div>
          </div>

          {/* RAG 引用溯源 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-shrink-0" style={{ minHeight: '120px' }}>
            <div className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <i className="ri-links-line text-teal-500"></i>引用溯源
            </div>
            {currentSources.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-gray-400 py-3">
                <i className="ri-search-eye-line text-2xl mb-1.5"></i>
                <div className="text-xs text-center">AI回答后将显示<br />引用来源</div>
              </div>
            ) : (
              <div className="space-y-2">
                {currentSources.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg border border-gray-100 hover:border-teal-200 hover:bg-teal-50 transition-colors cursor-pointer">
                    <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                      <i className={`text-base ${s.type === 'pdf' ? 'ri-file-pdf-line text-red-500' : s.type === 'video' ? 'ri-video-line text-purple-500' : 'ri-file-ppt-line text-orange-500'}`}></i>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-gray-800 leading-snug break-all">{s.name}</div>
                      {s.page > 0 && <div className="text-xs text-teal-600 mt-0.5">第 {s.page} 页</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
