import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { AiMarkdownContent } from '@/components/AiMarkdownContent';
import { AiProgressTimeline } from '@/components/AiProgressTimeline';
import { compactSourceFileName, formatSourceFilePages, summarizeSourcesByFile } from '@/lib/aiSources';
import { aiService } from '@/services/ai';
import { recommendationService } from '@/services/recommendations';
import type {
  AiAttachment as AttachedFile,
  AiAnswerMode,
  AiConversation as Conversation,
  AiKnowledgeBase,
  AiMessage as Message,
  AiMessageSource,
  AiProgressEvent,
  AiResponseStyle,
} from '@/types/ai';
import type { PersonalizedRecommendation } from '@/types/recommendation';

const ANSWER_MODES: Array<{ value: AiAnswerMode; label: string; title: string }> = [
  { value: 'auto', label: '自动', title: '自动判断是否需要检索课程资料' },
  { value: 'strict_course', label: '检索', title: '检索课程资料，资料不足时明确说明' },
  { value: 'quick_llm', label: '快速', title: '不检索课程资料，直接快速回答' },
];

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

const FALLBACK_RECOMMENDATIONS: PersonalizedRecommendation[] = [
  {
    id: 'fallback:tcp-handshake',
    targetId: 'tcp-handshake',
    type: 'material',
    title: 'TCP 三次握手与四次挥手',
    description: '适合补充复习传输层连接建立与释放过程。',
    relevance: 86,
    score: 0.86,
    surface: 'ai_panel',
    reason: '根据课程常见提问生成的备用推荐。',
    action: { type: 'ask_ai', label: '让 AI 讲解', payload: { prompt: '请讲解 TCP 三次握手与四次挥手的过程和区别' } },
  },
  {
    id: 'fallback:congestion',
    targetId: 'tcp-congestion',
    type: 'concept',
    title: 'TCP 拥塞控制',
    description: '重点理解慢启动、拥塞避免、快重传与快恢复。',
    relevance: 82,
    score: 0.82,
    surface: 'ai_panel',
    reason: '这是计算机网络课程中的高频核心知识点。',
    action: { type: 'ask_ai', label: '继续追问', payload: { prompt: '请用图示思路解释 TCP 拥塞控制的几个阶段' } },
  },
];

function getLocalRecommendations(messages: Message[]): PersonalizedRecommendation[] {
  if (messages.length === 0) return FALLBACK_RECOMMENDATIONS;
  const allText = messages.filter(m => m.role === 'user').map(m => m.content.toLowerCase()).join(' ');
  const scored = FALLBACK_RECOMMENDATIONS.map(r => {
    const keywordScore = ['tcp', '拥塞', '握手', '传输层'].filter(kw => allText.includes(kw.toLowerCase())).length;
    return { ...r, relevance: Math.min(99, r.relevance + keywordScore * 5), score: Math.min(0.99, r.score + keywordScore * 0.05) };
  });
  scored.sort((a, b) => b.relevance - a.relevance);
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

const fileTypeConfig: Record<AttachedFile['fileType'], { icon: string; color: string; bg: string }> = {
  image: { icon: 'ri-image-line', color: 'text-green-600', bg: 'bg-green-50' },
  pdf: { icon: 'ri-file-pdf-line', color: 'text-red-500', bg: 'bg-red-50' },
  docx: { icon: 'ri-file-word-line', color: 'text-sky-600', bg: 'bg-sky-50' },
  md: { icon: 'ri-markdown-line', color: 'text-gray-600', bg: 'bg-gray-100' },
  code: { icon: 'ri-code-s-slash-line', color: 'text-teal-600', bg: 'bg-teal-50' },
  other: { icon: 'ri-file-line', color: 'text-gray-500', bg: 'bg-gray-50' },
};

const DISLIKE_REASONS = ['回答不准确', '答非所问', '解释太复杂', '内容太简单', '与课程无关'];

type RightTab = 'quick' | 'recommend' | 'source';
type RightPanelMode = 'closed' | 'standard' | 'wide';

function getSourceIconClass(type: string) {
  if (type === 'pdf') return 'ri-file-pdf-line text-red-500';
  if (type === 'video') return 'ri-video-line text-violet-500';
  if (type === 'ppt' || type === 'pptx') return 'ri-file-ppt-line text-orange-500';
  if (type === 'image') return 'ri-image-line text-green-600';
  return 'ri-file-text-line text-teal-600';
}

export default function AIAssistant() {
  const { id: classId } = useParams<{ id: string }>();
  const [conversations, setConversations] = useState<Conversation[]>([]);

  const [activeConvId, setActiveConvId] = useState<number>(0);
  const [messages, setMessages] = useState<Message[]>([{ ...INIT_WELCOME }]);
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [progressSteps, setProgressSteps] = useState<AiProgressEvent[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [knowledgeBase, setKnowledgeBase] = useState<AiKnowledgeBase>('course');
  const [answerMode, setAnswerMode] = useState<AiAnswerMode>('auto');
  const [style, setStyle] = useState<AiResponseStyle>('academic');
  const [currentSources, setCurrentSources] = useState<AiMessageSource[]>([]);
  const [recommendations, setRecommendations] = useState<PersonalizedRecommendation[]>([]);
  const [showConvList, setShowConvList] = useState(true);
  const [rightTab, setRightTab] = useState<RightTab>('quick');
  const [rightPanelMode, setRightPanelMode] = useState<RightPanelMode>('standard');

  const [feedbackModal, setFeedbackModal] = useState<{ msgId: number } | null>(null);
  const [feedbackReason, setFeedbackReason] = useState('');
  const [feedbackReasonTag, setFeedbackReasonTag] = useState('');
  const [showFeedbackToast, setShowFeedbackToast] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshRecommendations = useCallback(async (surfaceQuery?: string, sourceMessages: Message[] = messages) => {
    try {
      const data = await recommendationService.getPersonalized(classId, 'ai_panel', {
        limit: 6,
        query: surfaceQuery,
      });
      setRecommendations(data.items.length > 0 ? data.items : getLocalRecommendations(sourceMessages));
    } catch (error) {
      console.warn('加载个性化推荐失败', error);
      setRecommendations(getLocalRecommendations(sourceMessages));
    }
  }, [classId, messages]);

  useEffect(() => {
    let mounted = true;

    const loadAiData = async () => {
      const [loadedConversations, loadedRecommendations] = await Promise.all([
        aiService.getStudentConversations(),
        recommendationService.getPersonalized(classId, 'ai_panel', { limit: 6 }).catch(() => null),
      ]);

      if (!mounted) {
        return;
      }

      setConversations(loadedConversations);
      setRecommendations(
        loadedRecommendations?.items?.length
          ? loadedRecommendations.items
          : getLocalRecommendations([]),
      );
    };

    loadAiData();

    return () => {
      mounted = false;
    };
  }, [classId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const autoResizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  useEffect(() => { autoResizeTextarea(); }, [input, autoResizeTextarea]);

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
    const ALLOWED_EXTS = ['.txt', '.md', '.markdown', '.py', '.js', '.ts', '.jsx', '.tsx', '.cpp', '.c', '.java', '.go', '.rs', '.yaml', '.yml', '.sh', '.php', '.rb', '.swift', '.kt', '.json', '.html', '.css', '.docx', '.doc'];
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
      newFiles.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, name: file.name, size: file.size, mimeType: file.type, fileType, preview, rawFile: file });
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

  const handleSelectConversation = async (convId: number) => {
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    setActiveConvId(convId);
    setMessages(conv.messages.length > 0 ? conv.messages : [{ ...INIT_WELCOME }]);
    setCurrentSources([]);
    setAttachedFiles([]);
    setRecommendations(getLocalRecommendations(conv.messages));

    try {
      const loadedMessages = await aiService.getConversationMessages('student', convId);
      setMessages(loadedMessages.length > 0 ? loadedMessages : conv.messages);
      await refreshRecommendations(undefined, loadedMessages.length > 0 ? loadedMessages : conv.messages);
    } catch (error) {
      console.error('加载历史会话失败', error);
      setMessages(conv.messages.length > 0 ? conv.messages : [{ ...INIT_WELCOME }]);
    }
  };

  const handleNewConversation = () => {
    setActiveConvId(0);
    setMessages([{ ...INIT_WELCOME, id: Date.now() }]);
    setInput('');
    setAttachedFiles([]);
    setCurrentSources([]);
    setRecommendations(getLocalRecommendations([]));
    void refreshRecommendations(undefined, []);
  };

  const handleKnowledgeBaseChange = async (value: AiKnowledgeBase) => {
    setKnowledgeBase(value);
    if (activeConvId === 0) {
      return;
    }
    await aiService.updateConversationContext({ conversationId: activeConvId, knowledgeBase: value });
  };

  const handleStyleChange = async (value: AiResponseStyle) => {
    setStyle(value);
    if (activeConvId === 0) {
      return;
    }
    await aiService.updateConversationStyle({ conversationId: activeConvId, style: value });
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

  const handleProgressEvent = useCallback((event: AiProgressEvent) => {
    setProgressSteps(prev => {
      const existingIndex = prev.findIndex(item => item.stage === event.stage);
      if (existingIndex < 0) return [...prev, event];
      return prev.map((item, index) => index === existingIndex ? { ...item, ...event } : item);
    });
  }, []);

  const handleCitationClick = useCallback((source: AiMessageSource) => {
    setCurrentSources(prev => [source, ...prev.filter(item => item.chunkId !== source.chunkId || item.name !== source.name)]);
    setRightTab('source');
    if (rightPanelMode === 'closed') {
      setRightPanelMode('standard');
    }
  }, [rightPanelMode]);

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
    setProgressSteps([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    try {
      const { conversation, reply } = await aiService.sendMessage('student', {
        conversationId: activeConvId || undefined,
        classId,
        content: text,
        attachments: userMsg.attachments,
        answerMode,
        onProgress: handleProgressEvent,
      });

      const finalMessages = [...nextMessages, reply];
      setMessages(finalMessages);
      setActiveConvId(conversation.id);
      setConversations(prev => {
        const existing = prev.find(item => item.id === conversation.id);
        const updatedConversation: Conversation = {
          ...conversation,
          title: existing?.title || conversation.title,
          createdAt: existing?.createdAt || conversation.createdAt,
          lastMessage: reply.content.slice(0, 40) + (reply.content.length > 40 ? '...' : ''),
          messages: finalMessages,
        };
        return existing
          ? prev.map(item => item.id === conversation.id ? updatedConversation : item)
          : [updatedConversation, ...prev];
      });
      if (reply.sources) {
        setCurrentSources(reply.sources);
        setRightTab('source');
        if (rightPanelMode === 'closed') {
          setRightPanelMode('standard');
        }
      }
      await refreshRecommendations(text, finalMessages);
      setProgressSteps([]);
    } catch (error) {
      console.error('ai_send_message_failed', error);
      const aiMsg: Message = {
        id: Date.now() + 1, role: 'ai',
        content: 'AI助教暂时不可用，请稍后重试。', time: getNow(),
      };
      const finalMessages = [...nextMessages, aiMsg];
      setMessages(finalMessages);
      setCurrentSources([]);
      setRecommendations(getLocalRecommendations(finalMessages));
      saveCurrentConversation(finalMessages);
      setProgressSteps([]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleDeleteConversation = async (convId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (activeConvId === convId) handleNewConversation();
    await aiService.deleteConversation('student', convId);
  };

  const handleLike = async (msgId: number) => {
    const updated = messages.map(m => m.id === msgId ? { ...m, feedback: 'like' as const } : m);
    setMessages(updated);
    saveCurrentConversation(updated);
    await aiService.likeMessage(msgId);
  };

  const handleDislikeClick = (msgId: number) => {
    setFeedbackModal({ msgId });
    setFeedbackReason('');
    setFeedbackReasonTag('');
  };

  const submitDislike = async () => {
    if (!feedbackModal) return;
    const updated = messages.map(m => m.id === feedbackModal.msgId ? { ...m, feedback: 'dislike' as const } : m);
    setMessages(updated);
    const reason = feedbackReasonTag ? `${feedbackReasonTag}${feedbackReason ? '：' + feedbackReason : ''}` : feedbackReason;
    await aiService.dislikeMessage(feedbackModal.msgId, reason);
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
    material: { icon: 'ri-file-text-line', color: 'text-sky-600', bg: 'bg-sky-50' },
    concept: { icon: 'ri-mind-map', color: 'text-teal-600', bg: 'bg-teal-50' },
    faq: { icon: 'ri-question-answer-line', color: 'text-indigo-600', bg: 'bg-indigo-50' },
    mistake: { icon: 'ri-error-warning-line', color: 'text-amber-600', bg: 'bg-amber-50' },
    flashcard: { icon: 'ri-stack-line', color: 'text-emerald-600', bg: 'bg-emerald-50' },
    path: { icon: 'ri-route-line', color: 'text-violet-600', bg: 'bg-violet-50' },
    task: { icon: 'ri-task-line', color: 'text-orange-600', bg: 'bg-orange-50' },
    followup: { icon: 'ri-chat-follow-up-line', color: 'text-pink-600', bg: 'bg-pink-50' },
  };

  const handleRecommendationClick = async (rec: PersonalizedRecommendation) => {
    void recommendationService.recordEvent({
      recommendation_type: rec.type,
      target_id: rec.targetId,
      event_type: 'click',
      class_id: classId,
      score: rec.score,
      extra_data: { surface: rec.surface, action: rec.action?.type },
    }).catch(() => undefined);

    const payload = rec.action?.payload || {};
    const prompt = typeof payload.prompt === 'string' ? payload.prompt : rec.description;
    if (rec.action?.type === 'ask_ai' && prompt) {
      setInput(prompt);
      textareaRef.current?.focus();
      return;
    }
    if (rec.type === 'concept') {
      setInput(`请结合课程资料讲解「${rec.title}」，并指出常见误区。`);
      textareaRef.current?.focus();
      return;
    }
    if (rec.type === 'faq') {
      setInput(`请围绕这个教师审核问答继续讲解：${rec.title}`);
      textareaRef.current?.focus();
    }
  };

  const rightTabs: { key: RightTab; label: string; icon: string }[] = [
    { key: 'quick', label: '工具', icon: 'ri-magic-line' },
    { key: 'recommend', label: '推荐', icon: 'ri-star-line' },
    { key: 'source', label: '溯源', icon: 'ri-links-line' },
  ];
  const isRightPanelWide = rightPanelMode === 'wide';

  const canSend = (input.trim() !== '' || attachedFiles.length > 0) && !isTyping;

  return (
    <div className="h-full max-w-full overflow-hidden">
      {/* Toast */}
      {showFeedbackToast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-5 py-3 bg-gray-900 text-white text-sm rounded-xl shadow-lg">
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
                  className={`px-3 py-1.5 text-xs rounded-full border transition-colors cursor-pointer whitespace-nowrap ${feedbackReasonTag === r ? 'bg-orange-500 text-white border-orange-500' : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-orange-300 hover:text-orange-600'}`}
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
                <p className="text-xs text-orange-700 leading-relaxed">提交后，该段对话将转交给课程教师查看并处理，帮助改进AI助教的回答质量。</p>
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={() => setFeedbackModal(null)} className="flex-1 px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors cursor-pointer whitespace-nowrap">取消</button>
              <button onClick={submitDislike} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-orange-500 rounded-xl hover:bg-orange-600 transition-colors cursor-pointer whitespace-nowrap">提交并转交教师</button>
            </div>
          </div>
        </div>
      )}
      <div className="flex h-full max-w-full min-h-0 flex-col gap-3 overflow-visible xl:flex-row">

        {/* 左侧对话列表 */}
        {showConvList && (
          <div className="relative flex w-full min-h-[240px] flex-col rounded-[26px] border border-gray-200 bg-white shadow-[0_16px_40px_rgba(148,163,184,0.10)] xl:min-h-0 xl:w-[210px] xl:flex-shrink-0">
            <div className="flex items-center gap-2 border-b border-gray-100 px-3 pt-3 pb-2.5 flex-shrink-0">
              <button
                onClick={handleNewConversation}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line text-base"></i>新建对话
              </button>
              <button
                onClick={() => setShowConvList(false)}
                className="h-9 w-9 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 cursor-pointer xl:hidden"
                title="收起列表"
              >
                <i className="ri-arrow-left-s-line text-base"></i>
              </button>
            </div>
            <button
              onClick={() => setShowConvList(false)}
              className="absolute -right-3.5 top-1/2 z-20 hidden h-14 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-400 shadow-[0_12px_28px_rgba(148,163,184,0.16)] transition-colors hover:border-teal-200 hover:text-teal-600 xl:flex cursor-pointer"
              title="收起列表"
            >
              <i className="ri-arrow-left-s-line text-lg"></i>
            </button>

            <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
              {activeConvId === 0 && (
                <div className="px-2.5 py-2 bg-teal-50 rounded-lg border border-teal-200 mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-teal-500 flex-shrink-0"></span>
                    <span className="text-xs font-semibold text-teal-700 truncate">新对话</span>
                  </div>
                  <div className="text-xs text-teal-500 mt-0.5 pl-3">进行中...</div>
                </div>
              )}

              {conversations.length > 0 && (
                <>
                  <div className="text-xs font-medium text-gray-400 px-2 pt-1 pb-1">历史对话</div>
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={`group relative px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${activeConvId === conv.id ? 'bg-teal-50 border border-teal-200' : 'hover:bg-gray-50 border border-transparent'}`}
                    >
                      <div className="flex items-start justify-between gap-1">
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs font-medium truncate ${activeConvId === conv.id ? 'text-teal-700' : 'text-gray-800'}`}>{conv.title}</div>
                          <div className="text-xs text-gray-400 mt-0.5">{conv.createdAt}</div>
                        </div>
                        <button
                          onClick={e => handleDeleteConversation(conv.id, e)}
                          className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all flex-shrink-0 mt-0.5"
                        >
                          <i className="ri-delete-bin-line text-xs"></i>
                        </button>
                      </div>
                    </div>
                  ))}
                </>
              )}
              {conversations.length === 0 && (
                <div className="soft-ai-empty mx-1.5 mt-3">
                  <div className="flex flex-col items-center text-center text-gray-500">
                    <div className="w-10 h-10 rounded-full bg-white/80 flex items-center justify-center mb-2">
                      <i className="ri-chat-new-line text-violet-500 text-lg"></i>
                    </div>
                    <div className="text-xs font-medium text-gray-700">还没有历史对话</div>
                    <div className="text-xs mt-1">点击上方“新建对话”开始提问</div>
                  </div>
                </div>
              )}
            </div>

            <div className="px-3 py-2.5 border-t border-gray-100 flex-shrink-0">
              <div className="text-xs text-gray-400 text-center">{conversations.length} 段历史对话</div>
            </div>
          </div>
        )}

        {!showConvList && (
          <>
            <button
              onClick={() => setShowConvList(true)}
              className="flex h-11 w-full items-center justify-center rounded-xl border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 cursor-pointer xl:hidden"
              title="展开列表"
            >
              <i className="ri-arrow-right-s-line text-lg"></i>
            </button>
            <div className="relative hidden xl:block xl:w-0 xl:flex-shrink-0">
              <button
                onClick={() => setShowConvList(true)}
                className="absolute -left-3.5 top-1/2 z-20 flex h-14 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-400 shadow-[0_12px_28px_rgba(148,163,184,0.16)] transition-colors hover:border-teal-200 hover:text-teal-600 cursor-pointer"
                title="展开列表"
              >
                <i className="ri-arrow-right-s-line text-lg"></i>
              </button>
            </div>
          </>
        )}

        {/* 主对话区 */}
        <div className="flex min-h-[360px] min-w-0 flex-1 flex-col rounded-xl border border-gray-200 bg-white xl:min-h-0">

          {/* 顶部栏 */}
          <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between gap-3 flex-wrap flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 flex items-center justify-center rounded-full bg-teal-500 text-white flex-shrink-0">
                <i className="ri-robot-line text-sm"></i>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900 leading-tight">
                  {activeConvId === 0 ? '新对话' : (conversations.find(c => c.id === activeConvId)?.title || '当前对话')}
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
                  <span className="text-xs text-gray-400">在线</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={knowledgeBase}
                onChange={e => handleKnowledgeBaseChange(e.target.value as AiKnowledgeBase)}
                className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-gray-50 cursor-pointer"
              >
                <option value="course">课程知识库</option>
                <option value="personal">个人知识库</option>
              </select>
              <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-0.5" title="回答模式">
                {ANSWER_MODES.map(mode => (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => setAnswerMode(mode.value)}
                    title={mode.title}
                    className={`px-2 py-1 text-xs rounded-md transition-colors ${answerMode === mode.value ? 'bg-white text-teal-700 shadow-sm' : 'text-gray-500 hover:text-gray-800'}`}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
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
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
            {messages.map(msg => (
              <div key={msg.id} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5 ${msg.role === 'ai' ? 'bg-teal-500' : 'bg-teal-700'}`}>
                  {msg.role === 'ai' ? <i className="ri-robot-line text-sm"></i> : <span>李</span>}
                </div>

                <div className={`max-w-[76%] flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {/* 附件 */}
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className={`flex flex-wrap gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {msg.attachments.map(f => {
                        const cfg = fileTypeConfig[f.fileType] || fileTypeConfig.other;
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

                  {/* 消息气泡 */}
                  {msg.content && (
                    <>
                    {msg.role === 'ai' && msg.routeMeta && (
                      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs">
                        <span className="inline-flex items-center gap-1 rounded-full border border-teal-100 bg-teal-50 px-2 py-0.5 text-teal-700">
                          <i className={msg.routeMeta.retrievalUsed ? 'ri-book-open-line' : 'ri-flashlight-line'}></i>
                          {msg.routeMeta.displayLabel || 'AI回答'}
                        </span>
                        {!msg.routeMeta.retrievalUsed && msg.routeMeta.route === 'quick_llm' && (
                          <span className="text-gray-400">未检索课程资料</span>
                        )}
                      </div>
                    )}
                    <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed space-y-0.5 ${
                      msg.role === 'ai'
                        ? 'bg-gray-50 text-gray-800 border border-gray-100 rounded-tl-sm'
                        : 'bg-teal-600 text-white rounded-tr-sm'
                    }`}>
                      {msg.role === 'ai'
                        ? <AiMarkdownContent content={msg.content} sources={msg.sources} onCitationClick={handleCitationClick} />
                        : renderContent(msg.content)}
                    </div>
                    </>
                  )}

                  {/* 引用来源标签 */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {summarizeSourcesByFile(msg.sources).slice(0, 4).map(source => (
                        <span key={source.key} className="flex items-center gap-1 px-2 py-0.5 bg-teal-50 border border-teal-100 rounded-full text-xs text-teal-700 cursor-pointer hover:bg-teal-100 transition-colors">
                          <i className={`text-sm ${getSourceIconClass(source.type)}`}></i>
                          {compactSourceFileName(source.name, 14)}
                          {formatSourceFilePages(source.pages) && ` · ${formatSourceFilePages(source.pages)}`}
                        </span>
                      ))}
                      {summarizeSourcesByFile(msg.sources).length > 4 && (
                        <span className="px-2 py-0.5 rounded-full border border-teal-100 bg-teal-50 text-xs text-teal-700">
                          +{summarizeSourcesByFile(msg.sources).length - 4} 个文件
                        </span>
                      )}
                    </div>
                  )}

                  {/* 底部：时间 + 反馈 */}
                  <div className={`flex items-center gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    <span className="text-xs text-gray-400">{msg.time}</span>
                    {msg.role === 'ai' && !msg.isWelcome && (
                      <>
                        {msg.feedback === undefined && (
                          <div className="flex items-center gap-0.5">
                            <button
                              onClick={() => handleLike(msg.id)}
                              className="w-6 h-6 flex items-center justify-center rounded-md text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors cursor-pointer"
                              title="有帮助"
                            >
                              <i className="ri-thumb-up-line text-xs"></i>
                            </button>
                            <button
                              onClick={() => handleDislikeClick(msg.id)}
                              className="w-6 h-6 flex items-center justify-center rounded-md text-gray-400 hover:text-orange-500 hover:bg-orange-50 transition-colors cursor-pointer"
                              title="不够好"
                            >
                              <i className="ri-thumb-down-line text-xs"></i>
                            </button>
                          </div>
                        )}
                        {msg.feedback === 'like' && (
                          <span className="flex items-center gap-1 text-xs text-green-600">
                            <i className="ri-thumb-up-fill text-xs"></i>有帮助
                          </span>
                        )}
                        {msg.feedback === 'dislike' && (
                          <span className="flex items-center gap-1 text-xs text-orange-500">
                            <i className="ri-thumb-down-fill text-xs"></i>已转交教师
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5">
                  <i className="ri-robot-line text-sm"></i>
                </div>
                <AiProgressTimeline steps={progressSteps} />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 快捷提问 */}
          <div className="px-4 pt-2 pb-1 border-t border-gray-100 flex gap-2 flex-wrap flex-shrink-0">
            {['TCP三次握手是什么？', 'HTTP和HTTPS的区别？', 'TCP拥塞控制算法？'].map((q, i) => (
              <button
                key={i}
                onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                className="px-2.5 py-1 text-xs text-teal-700 bg-teal-50 border border-teal-100 rounded-full hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap"
              >
                {q}
              </button>
            ))}
          </div>

          {/* 输入区 */}
          <div className="px-4 pb-4 pt-2 flex-shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx,.txt,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh,.php,.rb,.swift,.kt"
              onChange={handleFileInputChange}
              className="hidden"
            />
            <div
              className={`rounded-xl border transition-all ${isDragOver ? 'border-teal-400 bg-teal-50/60 ring-2 ring-teal-200' : 'border-gray-200 bg-gray-50 focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100'}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {attachedFiles.length > 0 && (
                <div className="px-3 pt-3 pb-2 flex flex-wrap gap-2 border-b border-gray-200/60">
                  {attachedFiles.map(f => {
                    const cfg = fileTypeConfig[f.fileType] || fileTypeConfig.other;
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
                        <button onClick={() => handleRemoveAttachment(f.id)} className="w-4 h-4 flex items-center justify-center text-gray-400 hover:text-red-500 cursor-pointer flex-shrink-0 ml-0.5">
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
                    className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-teal-600 hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-attachment-2 text-base"></i>
                  </button>
                  <button
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.accept = 'image/*';
                        fileInputRef.current.click();
                        setTimeout(() => { if (fileInputRef.current) fileInputRef.current.accept = 'image/*,.pdf,.doc,.docx,.txt,.md,.markdown'; }, 1000);
                      }
                    }}
                    title="上传图片"
                    className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-image-add-line text-base"></i>
                  </button>
                  <button
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.accept = '.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go,.rs,.html,.css,.json,.yaml,.yml,.sh,.php,.rb,.swift,.kt,.md';
                        fileInputRef.current.click();
                        setTimeout(() => { if (fileInputRef.current) fileInputRef.current.accept = 'image/*,.pdf,.doc,.docx,.txt,.md,.markdown'; }, 1000);
                      }
                    }}
                    title="上传代码文件"
                    className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-teal-600 hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    <i className="ri-code-s-slash-line text-base"></i>
                  </button>
                  {attachedFiles.length > 0 && (
                    <span className="text-xs text-gray-400 ml-1">已附 {attachedFiles.length} 个文件</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 hidden sm:block">Enter 发送</span>
                  <button
                    onClick={sendMessage}
                    disabled={!canSend}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${canSend ? 'bg-teal-600 text-white hover:bg-teal-700' : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
                  >
                    <i className="ri-send-plane-fill text-sm"></i>发送
                  </button>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-1.5 px-0.5">
              <i className="ri-information-line text-xs text-gray-400"></i>
              <span className="text-xs text-gray-400">支持图片、PDF、Word、Markdown、代码文件（≤20MB），可拖拽上传</span>
            </div>
          </div>
        </div>

        {/* 右侧面板 —— 可展开工作台 */}
        {rightPanelMode === 'closed' ? (
          <button
            onClick={() => setRightPanelMode('standard')}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-teal-100 bg-white text-xs font-medium text-teal-700 shadow-sm transition-colors hover:bg-teal-50 xl:h-auto xl:w-12 xl:flex-shrink-0 xl:flex-col xl:px-2 xl:py-4 cursor-pointer"
            title="展开辅助面板"
          >
            <i className="ri-sidebar-unfold-line text-base"></i>
            <span className="xl:[writing-mode:vertical-rl]">辅助面板</span>
          </button>
        ) : (
        <div className={`flex w-full min-h-[260px] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-[0_18px_42px_rgba(15,23,42,0.08)] transition-[width] duration-300 xl:min-h-0 xl:flex-shrink-0 ${isRightPanelWide ? 'xl:w-[520px] 2xl:w-[600px]' : 'xl:w-[236px]'}`}>
          <div className="flex items-center justify-end gap-2 border-b border-gray-100 px-3 py-1.5 flex-shrink-0">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setRightPanelMode(isRightPanelWide ? 'standard' : 'wide')}
                className="inline-flex h-7 items-center gap-1 rounded-lg border border-gray-200 px-2 text-xs font-medium text-gray-500 transition-colors hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700 cursor-pointer"
                title={isRightPanelWide ? '恢复标准宽度' : '展开为工作台'}
              >
                <i className={isRightPanelWide ? 'ri-contract-left-right-line' : 'ri-expand-left-right-line'}></i>
                <span className="hidden 2xl:inline">{isRightPanelWide ? '标准' : '展开'}</span>
              </button>
              <button
                onClick={() => setRightPanelMode('closed')}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-700 cursor-pointer"
                title="收起辅助面板"
              >
                <i className="ri-sidebar-fold-line text-base"></i>
              </button>
            </div>
          </div>

          {/* Tab 头 */}
          <div className="flex items-center border-b border-gray-100 px-2 pt-2 gap-1 flex-shrink-0">
            {rightTabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => setRightTab(tab.key)}
                className={`flex-1 flex items-center justify-center gap-1 py-2 text-xs font-medium rounded-t-lg transition-colors cursor-pointer whitespace-nowrap ${
                  rightTab === tab.key
                    ? 'text-teal-700 bg-teal-50 border-b-2 border-teal-500'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <i className={`${tab.icon} text-sm`}></i>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 内容 */}
          <div className="flex-1 overflow-y-auto">

            {/* 工具 Tab */}
            {rightTab === 'quick' && (
              <div className="p-4 space-y-4">
                {/* 快捷功能 */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">便捷功能</div>
                  <div className={`grid grid-cols-2 gap-2 ${isRightPanelWide ? 'xl:grid-cols-3' : ''}`}>
                    {quickPrompts.map((item, i) => (
                      <button
                        key={i}
                        onClick={() => { setInput(item.prompt); textareaRef.current?.focus(); }}
                        className="flex flex-col items-center gap-1.5 px-2 py-3 text-xs font-medium text-gray-700 bg-gray-50 rounded-xl hover:bg-teal-50 hover:text-teal-700 transition-colors cursor-pointer border border-transparent hover:border-teal-100"
                      >
                        <div className="w-8 h-8 flex items-center justify-center">
                          <i className={`${item.icon} ${item.color} text-lg`}></i>
                        </div>
                        <span className="text-center leading-tight">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 对话风格 */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">对话风格</div>
                  <div className="space-y-1.5">
                    {[
                      { value: 'academic', label: '严谨学术型', icon: 'ri-graduation-cap-line', desc: '精准、严谨' },
                      { value: 'inspire', label: '启发引导型', icon: 'ri-lightbulb-line', desc: '启发思考' },
                      { value: 'debug', label: 'Debug调试型', icon: 'ri-code-s-slash-line', desc: '适合编程' },
                    ].map(s => (
                      <label
                        key={s.value}
                        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-colors border ${style === s.value ? 'border-teal-300 bg-teal-50' : 'border-gray-100 hover:bg-gray-50'}`}
                      >
                        <input type="radio" name="ai-style-student" value={s.value} checked={style === s.value} onChange={() => handleStyleChange(s.value as AiResponseStyle)} className="w-3.5 h-3.5 accent-teal-600 flex-shrink-0" />
                        <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                          <i className={`${s.icon} text-sm ${style === s.value ? 'text-teal-600' : 'text-gray-400'}`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs font-medium leading-tight ${style === s.value ? 'text-teal-700' : 'text-gray-800'}`}>{s.label}</div>
                          <div className="text-xs text-gray-400 leading-tight mt-0.5">{s.desc}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 推荐 Tab */}
            {rightTab === 'recommend' && (
              <div className="p-4">
                <div className="text-xs text-gray-400 mb-3 flex items-center gap-1.5">
                  <i className="ri-star-line text-amber-400"></i>
                  根据当前课程、画像和最近提问推荐
                </div>
                {recommendations.length === 0 && (
                  <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/80 px-4 py-8 text-center">
                    <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-white text-gray-400">
                      <i className="ri-compass-3-line text-xl"></i>
                    </div>
                    <div className="text-xs font-medium text-gray-700">暂无个性化推荐</div>
                    <div className="mt-1 text-xs text-gray-400">多提几个课程问题后，这里会出现更贴合你的建议</div>
                  </div>
                )}
                <div className={`space-y-2 ${isRightPanelWide ? 'xl:grid xl:grid-cols-2 xl:gap-3 xl:space-y-0' : ''}`}>
                  {recommendations.map(rec => {
                    const iconInfo = resourceIcons[rec.type] || resourceIcons.material;
                    return (
                      <button
                        key={rec.id}
                        type="button"
                        onClick={() => handleRecommendationClick(rec)}
                        className="w-full text-left flex items-start gap-2.5 p-3 rounded-xl border border-gray-100 hover:border-teal-200 hover:bg-teal-50/40 cursor-pointer transition-colors group"
                      >
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${iconInfo.bg}`}>
                          <i className={`${iconInfo.icon} ${iconInfo.color} text-base`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-gray-800 leading-snug group-hover:text-teal-700 transition-colors line-clamp-2">{rec.title}</div>
                          <div className="text-xs text-gray-500 mt-1 line-clamp-2">{rec.description}</div>
                          <div className="text-xs text-gray-400 mt-1 line-clamp-2">{rec.reason}</div>
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <div className="h-1 flex-1 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-amber-400 rounded-full" style={{ width: `${rec.relevance}%` }}></div>
                            </div>
                            <span className="text-xs text-amber-600 font-medium flex-shrink-0">{rec.relevance}%</span>
                          </div>
                          <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-teal-600 border border-teal-100">
                            {rec.action?.label || '查看'}
                            <i className="ri-arrow-right-s-line text-xs"></i>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 溯源 Tab */}
            {rightTab === 'source' && (
              <div className="p-4">
                <div className="text-xs text-gray-400 mb-3 flex items-center gap-1.5">
                  <i className="ri-links-line text-teal-500"></i>
                  最新回答的引用来源
                </div>
                {currentSources.length === 0 ? (
                  <div className="soft-ai-empty flex flex-col items-center justify-center py-12 text-gray-500">
                    <div className="w-12 h-12 rounded-full bg-white/80 border border-white/70 flex items-center justify-center mb-2">
                      <i className="ri-search-eye-line text-2xl text-violet-500"></i>
                    </div>
                    <div className="text-xs text-center leading-relaxed font-medium text-gray-700">还没有可展示的溯源信息</div>
                    <div className="text-xs text-center leading-relaxed mt-1">AI回答后会自动展示引用资料和页码</div>
                  </div>
                ) : (
                  <div className={isRightPanelWide ? 'grid grid-cols-1 gap-3 xl:grid-cols-2' : 'space-y-2'}>
                    {summarizeSourcesByFile(currentSources).map(source => (
                      <div key={source.key} className="flex min-w-0 items-start gap-2.5 rounded-xl border border-gray-100 bg-gray-50 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50 cursor-pointer">
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                          <i className={`text-xl ${getSourceIconClass(source.type)}`}></i>
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="break-words text-xs font-medium leading-snug text-gray-800">{source.name}</div>
                          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                            {formatSourceFilePages(source.pages) && <span className="text-teal-600">{formatSourceFilePages(source.pages)}</span>}
                            <span className="text-gray-500">引用 {source.count} 处</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
