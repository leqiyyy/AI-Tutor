import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { AiMarkdownContent } from '@/components/AiMarkdownContent';
import { AiProgressTimeline } from '@/components/AiProgressTimeline';
import { compactSourceFileName, formatSourceFilePages, summarizeSourcesByFile } from '@/lib/aiSources';
import { getNameInitial } from '@/lib/display';
import { useAuth } from '@/hooks/use-auth';
import { aiService } from '@/services/ai';
import type {
  AiAttachment as AttachedFile,
  AiAnswerMode,
  AiConversation as Conversation,
  AiFeedbackItem as FeedbackItem,
  AiKnowledgeBase,
  AiMessage as Message,
  AiMessageSource,
  AiProgressEvent,
  AiResponseStyle,
  AiTeacherQuestion as AIQuestion,
} from '@/types/ai';

interface TeacherRecommendation {
  id: number;
  title: string;
  type: 'report' | 'template' | 'insight' | 'alert';
  desc: string;
  icon: string;
  iconColor: string;
  iconBg: string;
}

type TeacherToolAction = 'lessonPlan' | 'exam' | 'learningAnalysis' | 'flashcards';
type RightPanelMode = 'closed' | 'standard' | 'wide';

const ANSWER_MODES: Array<{ value: AiAnswerMode; label: string; title: string }> = [
  { value: 'auto', label: '自动', title: '自动判断走课程检索、直接回答或教师工具' },
  { value: 'strict_course', label: '检索', title: '检索课程资料，资料不足时明确说明' },
  { value: 'quick_llm', label: '快速', title: '不检索课程资料，直接快速回答' },
  { value: 'teacher_tool', label: '教学', title: '教案、出题、学情分析等任务优先走工具链' },
];

function getSourceIconClass(type: string) {
  if (type === 'pdf') return 'ri-file-pdf-line text-red-500';
  if (type === 'video') return 'ri-video-line text-amber-500';
  if (type === 'ppt' || type === 'pptx') return 'ri-file-ppt-line text-orange-500';
  if (type === 'image') return 'ri-image-line text-green-600';
  return 'ri-file-text-line text-teal-600';
}

function getFileType(file: File): AttachedFile['fileType'] {
  const name = file.name.toLowerCase();
  const mime = file.type;
  if (mime.startsWith('image/')) return 'image';
  if (mime === 'application/pdf') return 'pdf';
  if (mime.includes('word') || name.endsWith('.docx') || name.endsWith('.doc')) return 'docx';
  if (name.endsWith('.md')) return 'md';
  const codeExts = ['.py','.js','.ts','.jsx','.tsx','.cpp','.c','.java','.go','.rs','.html','.css','.json'];
  if (codeExts.some(e => name.endsWith(e))) return 'code';
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

const MOCK_AI_QUESTIONS: AIQuestion[] = [
  {
    id: 1,
    student: '张三',
    avatar: '张',
    question: 'TCP三次握手的第三次可以携带数据吗？',
    aiAnswer: '是的，TCP第三次握手（ACK报文）可以携带数据。连接在第三次握手时已进入ESTABLISHED状态，客户端已确认服务器的接收能力，因此可以开始传输应用层数据。但前两次握手不能携带数据。',
    confidence: 45,
    confidenceLevel: 'low',
    sources: [{ name: '第4章-传输层.pdf', page: 12 }],
    time: '10分钟前',
    status: 'pending',
  },
  {
    id: 2,
    student: '李四',
    avatar: '李',
    question: '子网掩码255.255.255.0对应的CIDR表示是什么？',
    aiAnswer: '255.255.255.0对应CIDR为/24。原因：转换为二进制共有24个连续的1（11111111.11111111.11111111.00000000），因此前缀长度为24。如192.168.1.0/24表示该网络有256个地址，可用主机地址254个。',
    confidence: 52,
    confidenceLevel: 'medium',
    sources: [{ name: '第3章-网络层.pdf', page: 15 }],
    time: '25分钟前',
    status: 'pending',
  },
  {
    id: 3,
    student: '王五',
    avatar: '王',
    question: 'HTTP和HTTPS的主要区别是什么？',
    aiAnswer: 'HTTP与HTTPS的主要区别：①安全性：HTTP明文传输，HTTPS通过TLS/SSL加密；②端口：HTTP默认80，HTTPS默认443；③证书：HTTPS需CA颁发数字证书；④性能：HTTPS有轻微加密开销；⑤SEO：HTTPS站点排名权重更高。',
    confidence: 78,
    confidenceLevel: 'high',
    sources: [{ name: '第5章-应用层.pdf', page: 8 }],
    time: '1小时前',
    status: 'adopted',
    teacherReply: '已采纳AI回答',
  },
  {
    id: 4,
    student: '赵六',
    avatar: '赵',
    question: 'Dijkstra算法和Bellman-Ford算法的使用场景有何不同？',
    aiAnswer: 'Dijkstra适用于边权重为正的网络，计算效率高（O(V²)），常用于OSPF协议。Bellman-Ford可处理负权重边，复杂度O(VE)较高，但能检测负权环，常用于RIP协议。大规模网络通常使用Dijkstra优化版。',
    confidence: 82,
    confidenceLevel: 'high',
    sources: [{ name: '第3章-网络层.pdf', page: 22 }],
    time: '2小时前',
    status: 'replied',
    teacherReply: '补充：实际的OSPF使用Dijkstra的改进版，感兴趣同学可查阅RFC2328。',
  },
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
  content: '您好！我是珞樱学堂AI助教，已加载《计算机网络》课程知识库。\n\n我可以帮您：解答课程疑问、生成教案试卷、分析学情数据。\n\n支持上传教材图片、Word文档、代码文件等，我会结合文件内容提供更精准的支持！',
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

function loadFeedbacks(): FeedbackItem[] {
  try {
    return JSON.parse(localStorage.getItem('luoying_ai_feedback') || '[]');
  } catch {
    return [];
  }
}

function stripReviewContext(value: string) {
  return value.replace(/\n\n\[review_context\][\s\S]*$/u, '').trim();
}

// ===== Feedback Detail Modal =====
function FeedbackDetailModal({ item, onClose, onResolve }: {
  item: FeedbackItem;
  onClose: () => void;
  onResolve: (id: string, teacherAnswer: string, addToKb: boolean) => Promise<void> | void;
}) {
  const [teacherAnswer, setTeacherAnswer] = useState(stripReviewContext(item.teacherAnswer || item.aiAnswer));
  const [addToKb, setAddToKb] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const cleanAiAnswer = stripReviewContext(item.aiAnswer);

  const submitResolve = async () => {
    if (!teacherAnswer.trim() || submitting) return;
    setSubmitting(true);
    try {
      await onResolve(item.id, teacherAnswer.trim(), addToKb);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose}></div>
      <div className="relative bg-white rounded-2xl w-[520px] max-h-[80vh] flex flex-col">
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
            <div className="text-sm text-gray-700 px-3 py-2.5 bg-gray-50 rounded-lg border border-gray-100 leading-relaxed max-h-40 overflow-y-auto">
              <AiMarkdownContent content={cleanAiAnswer} />
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">学生反馈原因</div>
            <div className="flex items-start gap-2 px-3 py-2.5 bg-orange-50 rounded-lg border border-orange-100">
              <i className="ri-feedback-line text-orange-500 text-sm mt-0.5 flex-shrink-0"></i>
              <span className="text-sm text-orange-800">{item.reason || '学生未填写具体原因'}</span>
            </div>
          </div>
          {item.status === 'pending' && (
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">教师纠正答案</div>
              <textarea
                value={teacherAnswer}
                onChange={event => setTeacherAnswer(event.target.value)}
                rows={7}
                className="w-full px-3 py-2.5 text-sm text-gray-800 bg-white border border-teal-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-200 resize-none leading-relaxed"
                placeholder="请填写教师确认后的标准答案..."
              />
              <label className="mt-2 flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={addToKb}
                  onChange={event => setAddToKb(event.target.checked)}
                  className="w-3.5 h-3.5 accent-teal-600"
                />
                审核通过后回流到课程知识库
              </label>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between flex-shrink-0">
          <div className={`flex items-center gap-1.5 text-xs font-medium ${item.status === 'resolved' ? 'text-green-600' : 'text-orange-500'}`}>
            <i className={item.status === 'resolved' ? 'ri-checkbox-circle-fill' : 'ri-time-line'}></i>
            {item.status === 'resolved' ? '已处理' : '待处理'}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors cursor-pointer whitespace-nowrap">关闭</button>
            {item.status === 'pending' && (
              <button
                onClick={() => { void submitResolve(); }}
                disabled={!teacherAnswer.trim() || submitting}
                className="px-4 py-2 text-sm font-medium text-white bg-teal-600 rounded-xl hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <i className="ri-check-line mr-1"></i>{submitting ? '提交中...' : '提交纠正'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ===== AI Question Panel =====
function AIQuestionsPanel({ questions, onUpdate, onAdopt, onReply, isWide = false }: {
  questions: AIQuestion[];
  onUpdate: (updated: AIQuestion[]) => void;
  onAdopt: (questionId: number) => Promise<void>;
  onReply: (questionId: number, reply: string) => Promise<void>;
  isWide?: boolean;
}) {
  const [filter, setFilter] = useState<'all' | 'pending' | 'adopted' | 'replied'>('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [replyingId, setReplyingId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');

  const filtered = filter === 'all' ? questions : questions.filter(q => q.status === filter);
  const pendingCount = questions.filter(q => q.status === 'pending').length;

  const adopt = async (id: number) => {
    await onAdopt(id);
    onUpdate(questions.map(q => q.id === id ? { ...q, status: 'adopted' as const, teacherReply: '已采纳AI回答' } : q));
  };

  const submitReply = async (id: number) => {
    if (!replyText.trim()) return;
    await onReply(id, replyText);
    onUpdate(questions.map(q => q.id === id ? { ...q, status: 'replied' as const, teacherReply: replyText } : q));
    setReplyingId(null);
    setReplyText('');
  };

  const confidenceMeta = (level: AIQuestion['confidenceLevel']) => {
    if (level === 'high') return { label: '高', color: 'text-green-600', bg: 'bg-green-50', bar: 'bg-green-500' };
    if (level === 'medium') return { label: '中', color: 'text-amber-600', bg: 'bg-amber-50', bar: 'bg-amber-400' };
    return { label: '低', color: 'text-red-500', bg: 'bg-red-50', bar: 'bg-red-400' };
  };

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-1 px-1 py-2 flex-shrink-0">
        {(['all', 'pending', 'adopted', 'replied'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 text-xs font-medium rounded-full transition-colors cursor-pointer whitespace-nowrap ${
              filter === f ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {f === 'all' ? `全部(${questions.length})` : f === 'pending' ? `待处理(${pendingCount})` : f === 'adopted' ? '已采纳' : '已回复'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 px-1">
        {filtered.length === 0 && (
          <div className="soft-ai-empty flex flex-col items-center justify-center py-10 text-gray-500">
            <div className="w-12 h-12 rounded-full bg-white/80 border border-white/70 flex items-center justify-center mb-2">
              <i className="ri-question-answer-line text-xl text-violet-500"></i>
            </div>
            <div className="text-xs font-medium text-gray-700">当前筛选下暂无问题</div>
            <div className="text-xs mt-1">可切换筛选项查看全部提问记录</div>
          </div>
        )}
        {filtered.map(q => {
          const meta = confidenceMeta(q.confidenceLevel);
          const isExpanded = expandedId === q.id;
          return (
            <div key={q.id} className={`rounded-xl border transition-colors ${isWide ? 'shadow-sm' : ''} ${
              q.status === 'pending' ? 'border-orange-100 bg-orange-50/40' : 'border-gray-100 bg-white'
            }`}>
              {/* Header */}
              <div
                className="px-3 py-2.5 cursor-pointer"
                onClick={() => setExpandedId(isExpanded ? null : q.id)}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0">{q.avatar}</div>
                    <span className="text-xs font-semibold text-gray-800">{q.student}</span>
                    <span className={`px-1.5 py-0.5 text-xs font-medium rounded-full ${meta.bg} ${meta.color}`}>AI置信度{meta.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {q.status === 'pending' && <span className="w-1.5 h-1.5 rounded-full bg-orange-500 flex-shrink-0"></span>}
                    {q.status === 'adopted' && <span className="text-xs text-green-600"><i className="ri-checkbox-circle-fill"></i></span>}
                    {q.status === 'replied' && <span className="text-xs text-teal-600"><i className="ri-chat-check-line"></i></span>}
                    <i className={isExpanded ? 'ri-arrow-up-s-line text-gray-400 text-sm' : 'ri-arrow-down-s-line text-gray-400 text-sm'}></i>
                  </div>
                </div>
                <div className={`text-xs text-gray-700 leading-relaxed ${isWide ? 'whitespace-normal' : 'truncate'}`}>{q.question}</div>
                <div className="text-xs text-gray-400 mt-1">{q.time}</div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className={`border-t border-gray-100 px-3 py-3 ${isWide ? 'space-y-4' : 'space-y-3'}`}>
                  {/* Confidence bar */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">AI置信度</span>
                      <span className="text-xs font-semibold text-gray-700">{q.confidence}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${meta.bar}`} style={{ width: `${q.confidence}%` }}></div>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {q.confidenceLevel === 'low' ? '置信度低，建议人工介入' : q.confidenceLevel === 'medium' ? '置信度中等，建议审核后采纳' : '置信度高，可直接采纳'}
                    </div>
                  </div>

                  {/* AI Answer */}
                  <div>
                    <div className="text-xs font-semibold text-gray-500 mb-1.5">AI 回答</div>
                    <div className={`text-xs text-gray-700 px-3 py-2.5 bg-teal-50/80 rounded-lg border border-teal-100 leading-relaxed whitespace-pre-wrap overflow-y-auto ${isWide ? 'max-h-[360px]' : 'max-h-32'}`}>{q.aiAnswer}</div>
                  </div>

                  {/* Sources */}
                  {q.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {q.sources.map((s, i) => (
                        <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-gray-50 border border-gray-200 rounded-full text-xs text-gray-600">
                          <i className="ri-file-pdf-line text-red-400 text-sm"></i>
                          {s.name} {s.page > 0 && `P${s.page}`}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Teacher reply display */}
                  {q.teacherReply && (
                    <div className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border ${q.status === 'adopted' ? 'bg-green-50 border-green-100' : 'bg-teal-50 border-teal-100'}`}>
                      <div className="w-5 h-5 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                        {q.status === 'adopted' ? <i className="ri-checkbox-circle-line text-xs"></i> : '王'}
                      </div>
                      <div>
                        <div className="text-xs font-medium text-gray-700 mb-0.5">{q.status === 'adopted' ? '采纳AI回答' : '教师回复'}</div>
                        <div className="text-xs text-gray-600">{q.teacherReply}</div>
                      </div>
                    </div>
                  )}

                  {/* Reply input */}
                  {replyingId === q.id && (
                    <div className="space-y-2">
                      <textarea
                        value={replyText}
                        onChange={e => setReplyText(e.target.value)}
                        placeholder="输入您的回复..."
                        rows={isWide ? 5 : 3}
                        className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none"
                      />
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => { setReplyingId(null); setReplyText(''); }} className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 cursor-pointer whitespace-nowrap">取消</button>
                        <button onClick={() => submitReply(q.id)} disabled={!replyText.trim()} className="px-3 py-1.5 text-xs font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 cursor-pointer whitespace-nowrap disabled:opacity-50">发送</button>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {q.status === 'pending' && replyingId !== q.id && (
                    <div className="flex items-center gap-2 pt-1">
                      <button onClick={() => adopt(q.id)} className="flex-1 px-3 py-2 text-xs font-medium text-green-700 bg-green-50 rounded-lg hover:bg-green-100 cursor-pointer whitespace-nowrap transition-colors">
                        <i className="ri-check-line mr-1"></i>采纳AI回答
                      </button>
                      <button onClick={() => { setReplyingId(q.id); setReplyText(''); }} className="flex-1 px-3 py-2 text-xs font-medium text-teal-700 bg-teal-50 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap transition-colors">
                        <i className="ri-edit-line mr-1"></i>自行回复
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ===== Main Component =====
export default function TeacherAIAssistant() {
  const { id: classId } = useParams<{ id: string }>();
  const { user } = useAuth();
  const avatarInitial = getNameInitial(user?.displayName || user?.name, '师');
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
  const [showConvList, setShowConvList] = useState(true);
  const [toolLoadingAction, setToolLoadingAction] = useState<TeacherToolAction | null>(null);
  const [toolResult, setToolResult] = useState<{ title: string; content: string } | null>(null);
  const [toolError, setToolError] = useState('');

  // Right panel tab
  const [rightTab, setRightTab] = useState<'feedback' | 'aiQuestions' | 'tools' | 'sources'>('aiQuestions');
  const [rightPanelMode, setRightPanelMode] = useState<RightPanelMode>('standard');

  // Student feedback
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [feedbackDetailItem, setFeedbackDetailItem] = useState<FeedbackItem | null>(null);

  // AI questions
  const [aiQuestions, setAIQuestions] = useState<AIQuestion[]>([]);

  const pendingFeedbackCount = feedbacks.filter(f => f.status === 'pending').length;
  const pendingQuestionCount = aiQuestions.filter(q => q.status === 'pending').length;

  useEffect(() => {
    let mounted = true;

    const loadAiData = async () => {
      try {
        const [loadedConversations, loadedFeedbacks, loadedQuestions] = await Promise.all([
          aiService.getTeacherConversations(),
          aiService.getFeedbackQueue(classId),
          aiService.getTeacherAiQuestions(),
        ]);

        if (!mounted) {
          return;
        }

        setConversations(loadedConversations);
        setFeedbacks(loadedFeedbacks);
        setAIQuestions(loadedQuestions);
      } catch {
        if (mounted) {
          setFeedbacks(loadFeedbacks());
          setAIQuestions(MOCK_AI_QUESTIONS);
        }
      }
    };

    loadAiData();
    const interval = setInterval(loadAiData, 3000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [classId]);

  const handleResolveFeedback = async (id: string, teacherAnswer: string, addToKb: boolean) => {
    const result = await aiService.resolveFeedback(id, teacherAnswer, addToKb);
    const syncResult = result && typeof result === 'object' ? result : undefined;
    const updated = feedbacks.map(f => f.id === id ? {
      ...f,
      status: 'resolved' as const,
      teacherAnswer,
      syncStatus: syncResult?.sync_status as FeedbackItem['syncStatus'],
      syncNote: syncResult?.sync_note,
    } : f);
    setFeedbacks(updated);
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

  useEffect(() => { autoResizeTextarea(); }, [input, autoResizeTextarea]);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const newFiles: AttachedFile[] = [];
    for (const file of fileArray) {
      if (file.size > 20 * 1024 * 1024) continue;
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

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) processFiles(e.dataTransfer.files);
  };

  const syncMessageSources = useCallback(async (
    aiMessage?: Message,
  ) => {
    if (!aiMessage || aiMessage.role !== 'ai') {
      setCurrentSources([]);
      return;
    }

    try {
      const loadedSources = await aiService.getMessageSources(aiMessage.id);
      setCurrentSources(loadedSources.length > 0 ? loadedSources : (aiMessage.sources ?? []));
    } catch {
      setCurrentSources(aiMessage.sources ?? []);
    }
  }, []);

  const handleSelectConversation = async (convId: number) => {
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    setActiveConvId(convId);
    setMessages(conv.messages.length > 0 ? conv.messages : [{ ...INIT_WELCOME }]);
    setCurrentSources([]);
    setAttachedFiles([]);
    try {
      const loadedMessages = await aiService.getConversationMessages('teacher', convId);
      const finalMessages = loadedMessages.length > 0 ? loadedMessages : conv.messages;
      setMessages(finalMessages);
      const latestAiMessage = [...finalMessages].reverse().find(msg => msg.role === 'ai' && !msg.isWelcome);
      void syncMessageSources(latestAiMessage);
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
    setToolError('');
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
        prev.map(c => c.id === activeConvId ? { ...c, messages: newMessages, lastMessage: lastAI ? lastAI.content.slice(0, 40) + '...' : c.lastMessage } : c)
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
    setRightTab('sources');
    if (rightPanelMode === 'closed') {
      setRightPanelMode('standard');
    }
  }, [rightPanelMode]);

  const runTeacherTool = async (
    action: TeacherToolAction,
    title: string,
    prompt: string,
  ) => {
    setToolLoadingAction(action);
    setToolError('');

    try {
      const result = action === 'lessonPlan'
        ? await aiService.generateLessonPlan({ prompt })
        : action === 'exam'
          ? await aiService.generateExam({ prompt })
          : action === 'learningAnalysis'
            ? await aiService.generateLearningAnalysis({ prompt })
            : await aiService.generateFlashcards({ prompt });

      setToolResult({ title, content: result });
    } catch {
      setToolError('工具结果生成失败，请稍后重试。');
    } finally {
      setToolLoadingAction(null);
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if ((!text && attachedFiles.length === 0) || isTyping) return;
    const userMsg: Message = { id: Date.now(), role: 'user', content: text, time: getNow(), attachments: attachedFiles.length > 0 ? [...attachedFiles] : undefined };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setAttachedFiles([]);
    setIsTyping(true);
    setProgressSteps([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    try {
      const { conversation, reply } = await aiService.sendMessage('teacher', {
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
      if (reply.role === 'ai') {
        void syncMessageSources(reply);
        if ((reply.sources?.length ?? 0) > 0) {
          setRightTab('sources');
          if (rightPanelMode === 'closed') {
            setRightPanelMode('standard');
          }
        }
      }
      setProgressSteps([]);
    } catch (error) {
      console.error('teacher_ai_send_message_failed', error);
      const aiMsg: Message = { id: Date.now() + 1, role: 'ai', content: 'AI助教暂时不可用，请稍后重试。', time: getNow() };
      const finalMessages = [...nextMessages, aiMsg];
      setMessages(finalMessages);
      setCurrentSources([]);
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
    await aiService.deleteConversation('teacher', convId);
  };

  const handleAdoptQuestion = async (questionId: number) => {
    await aiService.adoptAiAnswer(questionId);
    setAIQuestions(prev => prev.map(item => item.id === questionId ? { ...item, status: 'adopted', teacherReply: '已采纳AI回答' } : item));
  };

  const handleReplyQuestion = async (questionId: number, reply: string) => {
    await aiService.replyAiQuestion({ questionId, reply });
    setAIQuestions(prev => prev.map(item => item.id === questionId ? { ...item, status: 'replied', teacherReply: reply } : item));
  };

  const renderContent = (content: string) =>
    content.split('\n').map((line, i) => {
      const bold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return <p key={i} className={line === '' ? 'mt-1' : 'leading-relaxed'} dangerouslySetInnerHTML={{ __html: bold }} />;
    });

  const quickPrompts = [
    { label: '生成教案', icon: 'ri-file-text-line', color: 'text-teal-600', prompt: '请帮我生成本章节的教案大纲', action: 'lessonPlan' as const },
    { label: '生成试卷', icon: 'ri-file-list-line', color: 'text-green-600', prompt: '请帮我生成一份包含10道题的测验试卷', action: 'exam' as const },
    { label: '学情分析', icon: 'ri-bar-chart-line', color: 'text-amber-600', prompt: '请分析当前班级的整体学情状况', action: 'learningAnalysis' as const },
    { label: '生成卡组', icon: 'ri-flashlight-line', color: 'text-orange-600', prompt: '请为本章节生成学习闪卡卡组', action: 'flashcards' as const },
  ];

  const canSend = (input.trim() !== '' || attachedFiles.length > 0) && !isTyping;

  // Right panel tab config
  const rightTabs = [
    { key: 'aiQuestions' as const, label: 'AI问题', icon: 'ri-question-answer-line', badge: pendingQuestionCount },
    { key: 'feedback' as const, label: '学生反馈', icon: 'ri-feedback-line', badge: pendingFeedbackCount },
    { key: 'tools' as const, label: '工具', icon: 'ri-magic-line', badge: 0 },
    { key: 'sources' as const, label: '溯源', icon: 'ri-links-line', badge: 0 },
  ];
  const isRightPanelWide = rightPanelMode === 'wide';

  return (
    <div className="h-full max-w-full overflow-hidden">
      {feedbackDetailItem && (
        <FeedbackDetailModal item={feedbackDetailItem} onClose={() => setFeedbackDetailItem(null)} onResolve={handleResolveFeedback} />
      )}

      <div className="flex h-full max-w-full min-h-0 flex-col gap-3 overflow-visible xl:flex-row">
        {/* Left conversation list */}
        {showConvList && (
          <div className="relative flex w-full min-h-[240px] flex-col rounded-[26px] border border-gray-200 bg-white shadow-[0_16px_40px_rgba(148,163,184,0.10)] xl:min-h-0 xl:w-[210px] xl:flex-shrink-0">
            <div className="flex items-center gap-2 border-b border-gray-100 px-3 pt-3 pb-2.5 flex-shrink-0">
              <button onClick={handleNewConversation} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">
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
            <div className="flex-1 overflow-y-auto">
              {activeConvId === 0 && (
                <div className="mx-2 mt-2 px-3 py-2.5 bg-teal-50 rounded-lg border border-teal-200">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-teal-500 flex-shrink-0"></div>
                    <span className="text-xs font-semibold text-teal-700 truncate">新对话</span>
                  </div>
                  <div className="text-xs text-teal-600 mt-0.5">正在进行中...</div>
                </div>
              )}
              {conversations.length > 0 && (
                <div className="px-2 py-2 space-y-1">
                  <div className="text-xs font-medium text-gray-400 px-2 py-1">历史对话</div>
                  {conversations.map(conv => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={`group relative px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${activeConvId === conv.id ? 'bg-teal-50 border border-teal-200' : 'hover:bg-gray-50 border border-transparent'}`}
                    >
                      <div className="flex items-start justify-between gap-1">
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs font-medium truncate ${activeConvId === conv.id ? 'text-teal-700' : 'text-gray-800'}`}>{conv.title}</div>
                          <div className="text-xs text-gray-400 mt-0.5">{conv.createdAt}</div>
                        </div>
                        <button onClick={e => handleDeleteConversation(conv.id, e)} className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all flex-shrink-0">
                          <i className="ri-delete-bin-line text-xs"></i>
                        </button>
                      </div>
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

        {/* Main chat area */}
        <div className="flex min-h-[360px] min-w-0 flex-1 flex-col rounded-xl border border-gray-200 bg-white xl:min-h-0">
          {/* Chat header */}
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-3 flex-wrap flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 flex items-center justify-center rounded-full bg-teal-500 text-white">
                <i className="ri-robot-line text-base"></i>
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  {activeConvId === 0 ? '新对话' : conversations.find(c => c.id === activeConvId)?.title || '当前对话'}
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>
                  <span className="text-xs text-gray-500">在线</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select value={knowledgeBase} onChange={e => handleKnowledgeBaseChange(e.target.value as AiKnowledgeBase)} className="px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-400 bg-gray-50 cursor-pointer">
                <option value="course">计算机网络知识库</option>
                <option value="global">全局知识库</option>
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
              <button onClick={handleNewConversation} className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-teal-600 cursor-pointer rounded-md hover:bg-teal-50 transition-colors" title="新建对话">
                <i className="ri-add-circle-line text-sm"></i>
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {messages.map(msg => (
              <div key={msg.id} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs flex-shrink-0 ${msg.role === 'ai' ? 'bg-teal-500' : 'bg-gray-700'}`}>
                  {msg.role === 'ai' ? <i className="ri-robot-line"></i> : <span>{avatarInitial}</span>}
                </div>
                <div className={`max-w-[75%] flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
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
                    <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed space-y-0.5 ${msg.role === 'ai' ? 'bg-gray-50 text-gray-800 border border-gray-100 rounded-tl-sm' : 'bg-teal-600 text-white rounded-tr-sm'}`}>
                      {msg.role === 'ai'
                        ? <AiMarkdownContent content={msg.content} sources={msg.sources} onCitationClick={handleCitationClick} />
                        : renderContent(msg.content)}
                    </div>
                    </>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {summarizeSourcesByFile(msg.sources).slice(0, 4).map(source => (
                        <span key={source.key} className="flex items-center gap-1 px-2 py-0.5 bg-teal-50 border border-teal-100 rounded-full text-xs text-teal-700 cursor-pointer hover:bg-teal-100 transition-colors">
                          <i className={`text-base ${getSourceIconClass(source.type)}`}></i>
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
                  <span className="text-xs text-gray-400">{msg.time}</span>
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs flex-shrink-0">
                  <i className="ri-robot-line"></i>
                </div>
                <AiProgressTimeline steps={progressSteps} />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick prompts */}
          <div className="px-5 py-2 border-t border-gray-100 flex gap-2 flex-wrap flex-shrink-0">
            {['请帮我生成TCP三次握手教案', '请分析班级学情', '生成期中考试试卷'].map((q, i) => (
              <button key={i} onClick={() => { setInput(q); textareaRef.current?.focus(); }} className="px-2.5 py-1 text-xs text-teal-700 bg-teal-50 border border-teal-100 rounded-full hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap">
                {q}
              </button>
            ))}
          </div>

          {/* Input area */}
          <div className="px-4 pb-4 pt-2 flex-shrink-0">
            <input ref={fileInputRef} type="file" multiple accept="image/*,.pdf,.doc,.docx,.txt,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go" onChange={handleFileInputChange} className="hidden" />
            <div
              className={`rounded-xl border transition-all ${isDragOver ? 'border-teal-400 bg-teal-50/60 ring-2 ring-teal-200' : 'border-gray-200 bg-gray-50 focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-100'}`}
              onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
            >
              {attachedFiles.length > 0 && (
                <div className="px-3 pt-3 pb-2 flex flex-wrap gap-2 border-b border-gray-200/60">
                  {attachedFiles.map(f => {
                    const cfg = fileTypeConfig[f.fileType] || fileTypeConfig.other;
                    return (
                      <div key={f.id} className="group relative flex items-center gap-1.5 pl-2 pr-1 py-1 bg-white border border-gray-200 rounded-lg text-xs max-w-[180px]">
                        {f.fileType === 'image' && f.preview ? <img src={f.preview} alt={f.name} className="w-5 h-5 object-cover rounded flex-shrink-0" /> : <div className={`w-5 h-5 flex items-center justify-center rounded flex-shrink-0 ${cfg.bg}`}><i className={`${cfg.icon} ${cfg.color} text-xs`}></i></div>}
                        <span className="text-gray-700 font-medium truncate max-w-[100px]">{f.name}</span>
                        <button onClick={() => setAttachedFiles(prev => prev.filter(file => file.id !== f.id))} className="w-4 h-4 flex items-center justify-center text-gray-400 hover:text-red-500 cursor-pointer flex-shrink-0">
                          <i className="ri-close-line text-xs"></i>
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="px-3 py-2.5">
                <textarea ref={textareaRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder={isDragOver ? '松开鼠标上传文件...' : '输入问题，或拖拽文件 · Enter 发送，Shift+Enter 换行'} rows={1} disabled={isTyping} className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none resize-none leading-relaxed" style={{ minHeight: '36px', maxHeight: '120px' }} />
              </div>
              <div className="px-3 pb-2.5 flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <button onClick={() => fileInputRef.current?.click()} title="上传文件" className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-teal-600 hover:bg-teal-50 transition-colors cursor-pointer"><i className="ri-attachment-2 text-base"></i></button>
                  <button onClick={() => { if (fileInputRef.current) { fileInputRef.current.accept = 'image/*'; fileInputRef.current.click(); setTimeout(() => { if (fileInputRef.current) fileInputRef.current.accept = 'image/*,.pdf,.doc,.docx,.txt,.md,.markdown,.py,.js,.ts,.jsx,.tsx,.cpp,.c,.java,.go'; }, 1000); } }} title="上传图片" className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors cursor-pointer"><i className="ri-image-add-line text-base"></i></button>
                  {attachedFiles.length > 0 && <span className="text-xs text-gray-400 ml-1">已附 {attachedFiles.length} 个文件</span>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 hidden sm:block">Enter发送</span>
                  <button onClick={sendMessage} disabled={!canSend} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${canSend ? 'bg-teal-600 text-white hover:bg-teal-700' : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}>
                    <i className="ri-send-plane-fill text-sm"></i>发送
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right panel - expandable workspace */}
        {rightPanelMode === 'closed' ? (
          <button
            onClick={() => setRightPanelMode('standard')}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-teal-100 bg-white text-xs font-medium text-teal-700 shadow-sm transition-colors hover:bg-teal-50 xl:h-auto xl:w-12 xl:flex-shrink-0 xl:flex-col xl:px-2 xl:py-4 cursor-pointer"
            title="展开审核工作台"
          >
            <i className="ri-sidebar-unfold-line text-base"></i>
            <span className="xl:[writing-mode:vertical-rl]">审核工作台</span>
          </button>
        ) : (
        <div className={`flex w-full min-h-[260px] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-[0_18px_42px_rgba(15,23,42,0.08)] transition-[width] duration-300 xl:min-h-0 xl:flex-shrink-0 ${isRightPanelWide ? 'xl:w-[560px] 2xl:w-[640px]' : 'xl:w-[260px]'}`}>
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
                title="收起审核工作台"
              >
                <i className="ri-sidebar-fold-line text-base"></i>
              </button>
            </div>
          </div>

          {/* Tab header */}
          <div className="flex border-b border-gray-100 flex-shrink-0 px-1 pt-1">
            {rightTabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => setRightTab(tab.key)}
                className={`relative flex-1 flex flex-col items-center gap-0.5 py-2.5 text-xs font-medium transition-colors cursor-pointer rounded-t-lg ${
                  rightTab === tab.key ? 'text-teal-600 bg-teal-50/60' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <div className="relative w-5 h-5 flex items-center justify-center">
                  <i className={`${tab.icon} text-base`}></i>
                  {tab.badge > 0 && (
                    <span className="absolute -top-1 -right-1.5 flex items-center justify-center min-w-[14px] h-[14px] px-0.5 text-[10px] font-bold text-white bg-orange-500 rounded-full">
                      {tab.badge}
                    </span>
                  )}
                </div>
                <span className="text-[10px] leading-none">{tab.label}</span>
                {rightTab === tab.key && <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-6 h-0.5 bg-teal-500 rounded-full"></div>}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-hidden flex flex-col px-3 py-3">
            {/* AI Questions tab */}
            {rightTab === 'aiQuestions' && (
              <AIQuestionsPanel questions={aiQuestions} onUpdate={setAIQuestions} onAdopt={handleAdoptQuestion} onReply={handleReplyQuestion} isWide={isRightPanelWide} />
            )}

            {/* Feedback tab */}
            {rightTab === 'feedback' && (
              <div className="flex-1 overflow-y-auto">
                {feedbacks.length === 0 ? (
                  <div className="soft-ai-empty flex flex-col items-center justify-center py-10 text-gray-500">
                    <div className="w-12 h-12 rounded-full bg-white/80 border border-white/70 flex items-center justify-center mb-2">
                      <i className="ri-thumb-down-line text-xl text-violet-500"></i>
                    </div>
                    <div className="text-xs text-center font-medium text-gray-700">暂无学生点踩反馈</div>
                    <div className="text-xs text-center mt-1">当前 AI 回答质量稳定</div>
                  </div>
                ) : (
                  <div className={`space-y-2 ${isRightPanelWide ? 'xl:grid xl:grid-cols-2 xl:gap-3 xl:space-y-0' : ''}`}>
                    {feedbacks.map(item => (
                      <div
                        key={item.id}
                        onClick={() => setFeedbackDetailItem(item)}
                        className={`p-3 rounded-xl border cursor-pointer transition-colors ${item.status === 'pending' ? 'border-orange-100 bg-orange-50/60 hover:border-orange-300' : 'border-gray-100 bg-gray-50 hover:border-gray-200'}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5">
                            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.status === 'pending' ? 'bg-orange-500' : 'bg-gray-300'}`}></div>
                            <span className="text-xs font-medium text-gray-800">{item.studentName}</span>
                          </div>
                          <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${item.status === 'pending' ? 'bg-orange-100 text-orange-600' : 'bg-gray-100 text-gray-500'}`}>
                            {item.status === 'pending' ? '待处理' : '已处理'}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 truncate">{item.conversationTitle}</div>
                        {item.reason && <div className="text-xs text-gray-400 truncate mt-0.5">{item.reason}</div>}
                        <div className="text-xs text-gray-400 mt-1">{item.timestamp.split(' ')[0]}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tools tab */}
            {rightTab === 'tools' && (
              <div className="flex-1 overflow-y-auto space-y-4">
                {/* Quick tools */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">便捷功能</div>
                  <div className={`grid grid-cols-2 gap-2 ${isRightPanelWide ? 'xl:grid-cols-4' : ''}`}>
                    {quickPrompts.map((item, i) => (
                      <button
                        key={i}
                        onClick={() => { void runTeacherTool(item.action, item.label, item.prompt); }}
                        disabled={toolLoadingAction !== null}
                        className="flex flex-col items-center gap-1.5 px-2 py-3 text-xs font-medium text-gray-700 bg-gray-50 rounded-xl hover:bg-teal-50 hover:text-teal-700 transition-colors cursor-pointer border border-transparent hover:border-teal-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <i className={`${item.icon} ${toolLoadingAction === item.action ? 'text-teal-600' : item.color} text-lg`}></i>
                        <span>{toolLoadingAction === item.action ? '生成中...' : item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {(toolLoadingAction || toolResult || toolError) && (
                  <div>
                    <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">工具结果</div>
                    {toolLoadingAction && (
                      <div className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-3 text-xs text-blue-700">
                        正在生成 {quickPrompts.find((item) => item.action === toolLoadingAction)?.label ?? '内容'}...
                      </div>
                    )}
                    {toolError && (
                      <div className="rounded-xl border border-orange-100 bg-orange-50 px-3 py-3 text-xs text-orange-700">
                        {toolError}
                      </div>
                    )}
                    {toolResult && !toolLoadingAction && (
                      <div className="rounded-xl border border-teal-100 bg-teal-50/50 p-3">
                        <div className="text-xs font-semibold text-teal-700 mb-2">{toolResult.title}</div>
                        <div className={`overflow-y-auto whitespace-pre-wrap leading-relaxed text-gray-700 ${isRightPanelWide ? 'max-h-[360px] text-sm' : 'max-h-48 text-xs'}`}>
                          {toolResult.content}
                        </div>
                        <button
                          onClick={() => {
                            setInput(toolResult.content);
                            textareaRef.current?.focus();
                          }}
                          className="mt-3 inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-medium text-teal-700 border border-teal-200 hover:bg-teal-50 cursor-pointer whitespace-nowrap"
                        >
                          <i className="ri-edit-line"></i>写入输入框
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* AI style */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">对话风格</div>
                  <div className="space-y-1.5">
                    {[
                      { value: 'academic', label: '严谨学术型', icon: 'ri-graduation-cap-line', desc: '深度分析，引用知识库' },
                      { value: 'inspire', label: '启发引导型', icon: 'ri-lightbulb-line', desc: '以问题驱动思考' },
                      { value: 'debug', label: 'Debug调试型', icon: 'ri-code-s-slash-line', desc: '精准定位问题' },
                    ].map(s => (
                      <label key={s.value} className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-colors border ${style === s.value ? 'border-teal-200 bg-teal-50' : 'border-gray-100 hover:bg-gray-50'}`}>
                        <input type="radio" name="ai-style-teacher" value={s.value} checked={style === s.value} onChange={() => handleStyleChange(s.value as AiResponseStyle)} className="w-3.5 h-3.5 accent-teal-600" />
                        <i className={`${s.icon} text-sm ${style === s.value ? 'text-teal-600' : 'text-gray-500'}`}></i>
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs font-medium ${style === s.value ? 'text-teal-700' : 'text-gray-800'}`}>{s.label}</div>
                          <div className="text-xs text-gray-400 truncate">{s.desc}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Smart suggestions */}
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">智能建议</div>
                  <div className={`space-y-2 ${isRightPanelWide ? 'xl:grid xl:grid-cols-2 xl:gap-3 xl:space-y-0' : ''}`}>
                    {TEACHER_RECOMMENDATIONS.map(rec => (
                      <div key={rec.id} className="flex items-center gap-2.5 p-2.5 rounded-xl border border-gray-100 hover:border-teal-200 hover:bg-teal-50/40 cursor-pointer transition-colors">
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
              </div>
            )}

            {/* Sources tab */}
            {rightTab === 'sources' && (
              <div className="flex-1 overflow-y-auto">
                {currentSources.length === 0 ? (
                  <div className="soft-ai-empty flex flex-col items-center justify-center py-10 text-gray-500">
                    <div className="w-12 h-12 rounded-full bg-white/80 border border-white/70 flex items-center justify-center mb-2">
                      <i className="ri-search-eye-line text-xl text-violet-500"></i>
                    </div>
                    <div className="text-xs text-center font-medium text-gray-700">暂无可展示的引用来源</div>
                    <div className="text-xs text-center mt-1">当 AI 生成答案后会自动展示</div>
                  </div>
                ) : (
                  <div>
                    <div className="mb-2 text-xs text-gray-500">最新回答引用了以下文件：</div>
                    <div className={isRightPanelWide ? 'grid grid-cols-1 gap-3 xl:grid-cols-2' : 'space-y-2'}>
                      {summarizeSourcesByFile(currentSources).map(source => (
                        <div key={source.key} className="flex min-w-0 items-start gap-2 rounded-xl border border-gray-100 bg-gray-50 p-3 transition-colors hover:border-teal-200 hover:bg-teal-50 cursor-pointer">
                          <div className="w-7 h-7 flex items-center justify-center flex-shrink-0">
                            <i className={`text-lg ${getSourceIconClass(source.type)}`}></i>
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
