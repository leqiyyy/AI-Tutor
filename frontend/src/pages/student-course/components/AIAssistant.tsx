import { useState, useRef, useEffect, useCallback } from 'react';

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
  feedback?: 'like' | 'dislike';
  isWelcome?: boolean;
}

interface Conversation {
  id: number;
  title: string;
  createdAt: string;
  lastMessage: string;
  messages: Message[];
}

interface ResourceRecommendation {
  id: number;
  title: string;
  type: 'pdf' | 'video' | 'ppt' | 'exercise';
  chapter: string;
  relevance: number;
  reason: string;
  matchKeywords: string[];
}

export interface FeedbackItem {
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

const AI_RESPONSES: Record<string, { content: string; sources?: { name: string; page: number; type: string }[] }> = {
  default: {
    content: '这是一个很好的问题！根据课程知识库中的内容，我来为您详细解答。\n\n计算机网络是现代信息技术的基础，涵盖了从物理层到应用层的多个协议栈层次。如需了解具体某个知识点，欢迎继续提问。',
    sources: [{ name: '第1章-计算机网络概述.pdf', page: 3, type: 'pdf' }],
  },
  file: {
    content: '已收到您上传的文件，我正在解析内容...\n\n根据文件内容，我为您提取了以下关键信息：\n\n**主要知识点**\n• 文件内容已成功解析并关联到课程知识库\n• 我可以基于此文件内容回答您的问题\n• 如需深入分析某部分，请告诉我\n\n有什么想了解的内容吗？',
    sources: [{ name: '上传文件', page: 1, type: 'pdf' }],
  },
  tcp: {
    content: 'TCP三次握手过程如下：\n\n**第一次握手**：客户端发送SYN报文（SYN=1, seq=x），进入SYN_SENT状态。\n\n**第二次握手**：服务器收到后回复SYN+ACK报文（SYN=1, ACK=1, seq=y, ack=x+1），进入SYN_RCVD状态。\n\n**第三次握手**：客户端发送ACK报文（ACK=1, seq=x+1, ack=y+1），双方进入ESTABLISHED状态。\n\n第三次握手**可以携带数据**，但前两次不能携带数据。',
    sources: [
      { name: '第4章-传输层.pdf', page: 12, type: 'pdf' },
      { name: 'TCP协议详解视频.mp4', page: 0, type: 'video' },
    ],
  },
  http: {
    content: 'HTTP与HTTPS的主要区别：\n\n1. **安全性**：HTTP是明文传输，HTTPS通过TLS/SSL加密传输，防止数据被窃听和篡改。\n\n2. **端口**：HTTP默认使用80端口，HTTPS默认使用443端口。\n\n3. **证书**：HTTPS需要CA颁发的数字证书，用于身份验证。\n\n4. **性能**：HTTPS因加密解密有轻微性能开销，但现代硬件影响极小。',
    sources: [{ name: '第5章-应用层.pdf', page: 8, type: 'pdf' }],
  },
  subnet: {
    content: '子网掩码255.255.255.0的CIDR表示为 **/24**。\n\n原因：255.255.255.0转换为二进制是24个连续的1，即：\n`11111111.11111111.11111111.00000000`\n\n因此CIDR前缀长度为24，写作 `/24`。',
    sources: [{ name: '第3章-网络层.pdf', page: 15, type: 'pdf' }],
  },
  congestion: {
    content: 'TCP拥塞控制包含四个核心算法：\n\n**1. 慢启动（Slow Start）**：初始拥塞窗口cwnd=1，每收到一个ACK，cwnd翻倍增长，呈指数增长。\n\n**2. 拥塞避免（Congestion Avoidance）**：当cwnd达到慢启动阈值ssthresh后，改为线性增长，每个RTT增加1个MSS。\n\n**3. 快速重传（Fast Retransmit）**：收到3个重复ACK时，立即重传丢失的报文段。\n\n**4. 快速恢复（Fast Recovery）**：快速重传后，ssthresh设为cwnd/2，cwnd设为ssthresh。',
    sources: [{ name: '第4章-传输层.pdf', page: 18, type: 'pdf' }],
  },
};

function getAIResponse(input: string, hasFiles: boolean) {
  if (hasFiles) return AI_RESPONSES.file;
  const lower = input.toLowerCase();
  if (lower.includes('tcp') && (lower.includes('握手') || lower.includes('三次'))) return AI_RESPONSES.tcp;
  if (lower.includes('http') || lower.includes('https')) return AI_RESPONSES.http;
  if (lower.includes('子网') || lower.includes('255') || lower.includes('cidr')) return AI_RESPONSES.subnet;
  if (lower.includes('拥塞') || lower.includes('慢启动') || lower.includes('快速重传')) return AI_RESPONSES.congestion;
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

const ALL_RESOURCES: ResourceRecommendation[] = [
  { id: 1, title: 'TCP三次握手与四次挥手详解', type: 'video', chapter: '第5章 传输层', relevance: 96, reason: '与您的TCP提问高度相关', matchKeywords: ['TCP', '握手', '连接'] },
  { id: 2, title: '第5章 传输层.pdf', type: 'pdf', chapter: '第5章 传输层', relevance: 92, reason: '包含本次问题的详细讲解', matchKeywords: ['TCP', 'UDP', '传输层'] },
  { id: 3, title: 'HTTP/HTTPS协议深入解析', type: 'pdf', chapter: '第6章 应用层', relevance: 88, reason: '应用层协议综合资料', matchKeywords: ['HTTP', 'HTTPS', '应用层'] },
  { id: 4, title: '子网划分练习题集', type: 'exercise', chapter: '第4章 网络层', relevance: 85, reason: '包含大量子网掩码计算题', matchKeywords: ['子网', 'CIDR', 'IP地址'] },
  { id: 5, title: '网络层IP协议精讲.pptx', type: 'ppt', chapter: '第4章 网络层', relevance: 82, reason: '与当前学习进度匹配', matchKeywords: ['IP', '网络层', '路由'] },
  { id: 6, title: 'TCP拥塞控制算法动画', type: 'video', chapter: '第5章 传输层', relevance: 90, reason: '动画演示拥塞控制过程', matchKeywords: ['拥塞', '慢启动', '快速重传'] },
];

function getRecommendations(messages: Message[]): ResourceRecommendation[] {
  if (messages.length === 0) return ALL_RESOURCES.slice(0, 3);
  const allText = messages.filter(m => m.role === 'user').map(m => m.content.toLowerCase()).join(' ');
  const scored = ALL_RESOURCES.map(r => {
    const keywordScore = r.matchKeywords.filter(kw => allText.includes(kw.toLowerCase())).length;
    return { ...r, score: keywordScore * 20 + r.relevance };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, 4);
}

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
  content: '您好！我是珞樱学堂AI助教，已加载《计算机网络》课程知识库。\n\n我可以帮您：解答课程疑问、生成学习闪卡、分析薄弱知识点。\n\n支持上传图片、文档、代码等文件，我会结合文件内容为您解答！',
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

const DISLIKE_REASONS = [
  '回答不准确', '答非所问', '解释太复杂', '内容太简单', '与课程无关',
];

export default function AIAssistant() {
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: 1, title: 'TCP三次握手是什么？',
      createdAt: formatDate(new Date(Date.now() - 86400000)),
      lastMessage: 'TCP三次握手过程详解...',
      messages: [
        { ...INIT_WELCOME, id: 1 },
        { id: 2, role: 'user', content: 'TCP三次握手是什么？', time: '09:10' },
        { id: 3, ...AI_RESPONSES.tcp, role: 'ai', time: '09:10' },
      ],
    },
    {
      id: 2, title: 'HTTP和HTTPS的区别',
      createdAt: formatDate(new Date(Date.now() - 172800000)),
      lastMessage: 'HTTP是明文传输，HTTPS通过TLS/SSL...',
      messages: [
        { ...INIT_WELCOME, id: 1 },
        { id: 2, role: 'user', content: 'HTTP和HTTPS的区别是什么？', time: '14:30' },
        { id: 3, ...AI_RESPONSES.http, role: 'ai', time: '14:31' },
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
  const [recommendations, setRecommendations] = useState<ResourceRecommendation[]>(getRecommendations([]));
  const [showConvList, setShowConvList] = useState(true);

  // Feedback state
  const [feedbackModal, setFeedbackModal] = useState<{ msgId: number } | null>(null);
  const [feedbackReason, setFeedbackReason] = useState('');
  const [feedbackReasonTag, setFeedbackReasonTag] = useState('');
  const [showFeedbackToast, setShowFeedbackToast] = useState(false);

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
    setRecommendations(getRecommendations(conv.messages));
  };

  const handleNewConversation = () => {
    setActiveConvId(0);
    setMessages([{ ...INIT_WELCOME, id: Date.now() }]);
    setInput('');
    setAttachedFiles([]);
    setCurrentSources([]);
    setRecommendations(getRecommendations([]));
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
    setRecommendations(getRecommendations(finalMessages));
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

  // Feedback handlers
  const handleLike = (msgId: number) => {
    const updated = messages.map(m => m.id === msgId ? { ...m, feedback: 'like' as const } : m);
    setMessages(updated);
    saveCurrentConversation(updated);
  };

  const handleDislikeClick = (msgId: number) => {
    setFeedbackModal({ msgId });
    setFeedbackReason('');
    setFeedbackReasonTag('');
  };

  const submitDislike = () => {
    if (!feedbackModal) return;
    const updated = messages.map(m => m.id === feedbackModal.msgId ? { ...m, feedback: 'dislike' as const } : m);
    setMessages(updated);

    const aiMsg = messages.find(m => m.id === feedbackModal.msgId);
    const msgIdx = messages.findIndex(m => m.id === feedbackModal.msgId);
    const prevMsg = msgIdx > 0 ? messages.slice(0, msgIdx).reverse().find(m => m.role === 'user') : null;

    const convTitle = activeConvId === 0
      ? '当前对话'
      : (conversations.find(c => c.id === activeConvId)?.title || '对话');

    const feedbackItem: FeedbackItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      studentName: '李同学',
      conversationTitle: convTitle,
      questionContent: prevMsg?.content || '（无上文问题）',
      aiAnswer: aiMsg?.content || '',
      reason: feedbackReasonTag ? `${feedbackReasonTag}${feedbackReason ? '：' + feedbackReason : ''}` : feedbackReason,
      timestamp: new Date().toLocaleString('zh-CN'),
      status: 'pending',
      courseId: 'cs-network-2024',
    };

    const existing: FeedbackItem[] = JSON.parse(localStorage.getItem('luoying_ai_feedback') || '[]');
    localStorage.setItem('luoying_ai_feedback', JSON.stringify([feedbackItem, ...existing]));

    saveCurrentConversation(updated);
    setFeedbackModal(null);
    setShowFeedbackToast(true);
    setTimeout(() => setShowFeedbackToast(false), 3500);
  };

  const renderContent = (content: string) =>
    content.split('\n').map((line, i) => {
      const bold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return <p key={i} className={line === '' ? 'mt-1' : 'leading-relaxed'} dangerouslySetInnerHTML={{ __html: bold }} />;
    });

  const quickPrompts = [
    { label: '生成学习闪卡', icon: 'ri-stack-line', color: 'text-teal-600', prompt: '请帮我生成本章节的学习闪卡' },
    { label: '生成思维导图', icon: 'ri-mind-map', color: 'text-green-600', prompt: '请为本章节生成思维导图' },
    { label: '生成学习摘要', icon: 'ri-file-list-3-line', color: 'text-amber-600', prompt: '请生成本章节的学习摘要' },
    { label: '薄弱点分析', icon: 'ri-bar-chart-line', color: 'text-orange-600', prompt: '请分析我的薄弱知识点' },
  ];

  const resourceIcons: Record<string, { icon: string; color: string; bg: string }> = {
    pdf: { icon: 'ri-file-pdf-line', color: 'text-red-500', bg: 'bg-red-50' },
    video: { icon: 'ri-video-line', color: 'text-purple-500', bg: 'bg-purple-50' },
    ppt: { icon: 'ri-file-ppt-line', color: 'text-orange-500', bg: 'bg-orange-50' },
    exercise: { icon: 'ri-file-list-3-line', color: 'text-green-500', bg: 'bg-green-50' },
  };

  const canSend = (input.trim() !== '' || attachedFiles.length > 0) && !isTyping;

  return (
    <div className="max-w-full">
      {/* Toast */}
      {showFeedbackToast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-5 py-3 bg-gray-900 text-white text-sm rounded-xl shadow-lg animate-fade-in">
          <i className="ri-checkbox-circle-fill text-green-400 text-base"></i>
          已转交教师处理，感谢您的反馈！
        </div>
      )}

      {/* Dislike Modal */}
      {feedbackModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setFeedbackModal(null)}></div>
          <div className="relative bg-white rounded-2xl shadow-xl w-[400px] p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 flex items-center justify-center rounded-full bg-orange-50">
                <i className="ri-thumb-down-line text-orange-500 text-lg"></i>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">回答质量反馈</div>
                <div className="text-xs text-gray-500">请告诉我们哪里不够好</div>
              </div>
            </div>

            <div className="text-xs text-gray-500 mb-2">选择问题类型（可选）</div>
            <div className="flex flex-wrap gap-2 mb-4">
              {DISLIKE_REASONS.map(r => (
                <button
                  key={r}
                  onClick={() => setFeedbackReasonTag(prev => prev === r ? '' : r)}
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors cursor-pointer whitespace-nowrap ${
                    feedbackReasonTag === r
                      ? 'bg-orange-500 text-white border-orange-500'
                      : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-orange-300 hover:text-orange-600'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>

            <div className="text-xs text-gray-500 mb-2">补充说明（可选）</div>
            <textarea
              value={feedbackReason}
              onChange={e => setFeedbackReason(e.target.value)}
              placeholder="请描述AI助教的问题，帮助教师了解情况..."
              rows={3}
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none bg-gray-50"
            />

            <div className="mt-4 p-3 bg-orange-50 rounded-xl border border-orange-100">
              <div className="flex items-start gap-2">
                <i className="ri-information-line text-orange-500 text-sm mt-0.5"></i>
                <p className="text-xs text-orange-700 leading-relaxed">
                  提交后，该段对话将转交给课程教师查看并处理，帮助改进AI助教的回答质量。
                </p>
              </div>
            </div>

            <div className="flex gap-3 mt-5">
              <button
                onClick={() => setFeedbackModal(null)}
                className="flex-1 px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors cursor-pointer whitespace-nowrap"
              >
                取消
              </button>
              <button
                onClick={submitDislike}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-orange-500 rounded-xl hover:bg-orange-600 transition-colors cursor-pointer whitespace-nowrap"
              >
                提交并转交教师
              </button>
            </div>
          </div>
        </div>
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
                <option value="course">课程知识库</option>
                <option value="personal">个人知识库</option>
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
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 ${msg.role === 'ai' ? 'bg-teal-500' : 'bg-teal-700'}`}>
                  {msg.role === 'ai' ? <i className="ri-robot-line"></i> : <span>李</span>}
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

                  {/* 点赞点踩区域 - 仅AI非欢迎消息 */}
                  {msg.role === 'ai' && !msg.isWelcome && (
                    <div className="flex items-center gap-1 mt-0.5">
                      {msg.feedback === undefined && (
                        <>
                          <button
                            onClick={() => handleLike(msg.id)}
                            className="w-6 h-6 flex items-center justify-center rounded-md text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors cursor-pointer"
                            title="这个回答有帮助"
                          >
                            <i className="ri-thumb-up-line text-sm"></i>
                          </button>
                          <button
                            onClick={() => handleDislikeClick(msg.id)}
                            className="w-6 h-6 flex items-center justify-center rounded-md text-gray-400 hover:text-orange-500 hover:bg-orange-50 transition-colors cursor-pointer"
                            title="这个回答不够好"
                          >
                            <i className="ri-thumb-down-line text-sm"></i>
                          </button>
                        </>
                      )}
                      {msg.feedback === 'like' && (
                        <div className="flex items-center gap-1 text-xs text-green-600">
                          <i className="ri-thumb-up-fill text-sm"></i>
                          <span>有帮助</span>
                        </div>
                      )}
                      {msg.feedback === 'dislike' && (
                        <div className="flex items-center gap-1 text-xs text-orange-500">
                          <i className="ri-thumb-down-fill text-sm"></i>
                          <span>已转交教师处理</span>
                        </div>
                      )}
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
            {['TCP三次握手是什么？', 'HTTP和HTTPS的区别？', 'TCP拥塞控制算法有哪些？'].map((q, i) => (
              <button
                key={i}
                onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                className="px-2.5 py-1 text-xs text-teal-700 bg-teal-50 border border-teal-100 rounded-full hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap"
              >
                {q}
              </button>
            ))}
          </div>

          {/* 输入区域 */}
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
        <div className="flex flex-col gap-3" style={{ width: '240px', flexShrink: 0 }}>
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
                  <input type="radio" name="ai-style-student" value={s.value} checked={style === s.value} onChange={() => setStyle(s.value)} className="w-3.5 h-3.5 accent-teal-600" />
                  <i className={`${s.icon} text-sm ${style === s.value ? 'text-teal-600' : 'text-gray-500'}`}></i>
                  <span className={`text-xs font-medium ${style === s.value ? 'text-teal-700' : 'text-gray-800'}`}>{s.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 个性化资源推荐 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-shrink-0">
            <div className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <i className="ri-recommend-line text-amber-500"></i>个性化推荐
            </div>
            <div className="text-xs text-gray-400 mb-3">根据您的对话智能推荐</div>
            <div className="space-y-2">
              {recommendations.map(rec => {
                const iconInfo = resourceIcons[rec.type];
                return (
                  <div key={rec.id} className="flex items-start gap-2 p-2 rounded-lg border border-gray-100 hover:border-teal-200 hover:bg-teal-50/40 cursor-pointer transition-colors group">
                    <div className={`w-7 h-7 flex items-center justify-center rounded-md flex-shrink-0 ${iconInfo.bg}`}>
                      <i className={`${iconInfo.icon} ${iconInfo.color} text-sm`}></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gray-800 truncate group-hover:text-teal-700 transition-colors">{rec.title}</div>
                      <div className="text-xs text-gray-400 mt-0.5 truncate">{rec.reason}</div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <div className="h-1 flex-1 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-400 rounded-full" style={{ width: `${rec.relevance}%` }}></div>
                        </div>
                        <span className="text-xs text-amber-600 font-medium">{rec.relevance}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* RAG 引用溯源 */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex-1 min-h-0 flex flex-col">
            <div className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2 flex-shrink-0">
              <i className="ri-links-line text-teal-500"></i>引用溯源
            </div>
            {currentSources.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
                <i className="ri-search-eye-line text-3xl mb-2"></i>
                <div className="text-xs text-center">AI回答后将显示<br />引用来源</div>
              </div>
            ) : (
              <div className="space-y-2 overflow-y-auto flex-1">
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
