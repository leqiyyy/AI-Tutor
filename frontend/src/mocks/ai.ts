import { appEnv } from "@/lib/env";
import type {
  AiAttachment,
  AiConversation,
  AiFeedbackItem,
  AiMessage,
  AiMessageSource,
  AiResourceRecommendation,
  AiResponseStyle,
  AiTeacherQuestion,
  AiKnowledgeBase,
  ConversationContextPayload,
  ConversationStylePayload,
  CreateConversationPayload,
  GenerateTeacherToolPayload,
  ReplyAiQuestionPayload,
  SendMessagePayload,
  SubmitFeedbackPayload,
} from "@/types/ai";

// 用途: AIAssistant.tsx / TeacherAIAssistant.tsx 联调前的会话、问题队列、反馈队列模拟数据
// 页面来源: 学生 AI 助教、教师 AI 助教
// 未来接口归属: aiService.*

async function waitForMockLatency() {
  await new Promise((resolve) => setTimeout(resolve, appEnv.mockLatencyMs));
}

const studentAiSources: AiMessageSource[] = [
  { name: "第4章-传输层.pdf", page: 12, type: "pdf" },
];

const teacherAiSources: AiMessageSource[] = [
  { name: "班级学情报告.pdf", page: 1, type: "pdf" },
];

const studentWelcome: AiMessage = {
  id: 1,
  role: "ai",
  content:
    "您好！我是珞樱学堂AI助教，已加载《计算机网络》课程知识库。我可以帮您答疑、推荐资料和分析薄弱知识点。",
  time: "09:00",
  isWelcome: true,
};

const teacherWelcome: AiMessage = {
  id: 1,
  role: "ai",
  content:
    "您好！我是教师侧AI助教。我可以帮您整理答疑、生成教案和分析班级学情。",
  time: "09:00",
  isWelcome: true,
};

const studentConversationStore: AiConversation[] = [
  {
    id: 1,
    title: "TCP三次握手是什么？",
    createdAt: "昨天",
    lastMessage: "TCP三次握手过程详解...",
    messages: [
      studentWelcome,
      { id: 2, role: "user", content: "TCP三次握手是什么？", time: "09:10" },
      {
        id: 3,
        role: "ai",
        content:
          "TCP三次握手用于建立可靠连接，过程是 SYN -> SYN+ACK -> ACK。第三次握手时连接进入 ESTABLISHED，可开始传输应用层数据。",
        time: "09:10",
        sources: studentAiSources,
      },
    ],
  },
  {
    id: 2,
    title: "HTTP和HTTPS的区别",
    createdAt: "4月18日",
    lastMessage: "HTTPS通过TLS/SSL加密...",
    messages: [
      studentWelcome,
      { id: 2, role: "user", content: "HTTP和HTTPS的区别是什么？", time: "14:30" },
      {
        id: 3,
        role: "ai",
        content:
          "HTTP是明文传输，HTTPS通过TLS/SSL加密；默认端口分别是80和443，HTTPS还需要证书验证。",
        time: "14:31",
        sources: [{ name: "第5章-应用层.pdf", page: 8, type: "pdf" }],
      },
    ],
  },
];

const teacherConversationStore: AiConversation[] = [
  {
    id: 101,
    title: "班级学情分析",
    createdAt: "今天",
    lastMessage: "本班平均进度75%...",
    messages: [
      teacherWelcome,
      { id: 2, role: "user", content: "请分析本班本周学情", time: "10:00" },
      {
        id: 3,
        role: "ai",
        content:
          "本班68名学生平均学习进度75%，其中 TCP拥塞控制、子网划分是两个主要薄弱点，建议安排一次专项练习。",
        time: "10:01",
        sources: teacherAiSources,
      },
    ],
  },
];

const recommendationStore: AiResourceRecommendation[] = [
  {
    id: 1,
    title: "TCP三次握手与四次挥手详解",
    type: "video",
    chapter: "第5章 传输层",
    relevance: 96,
    reason: "与当前对话主题高度相关",
    matchKeywords: ["TCP", "握手", "连接"],
  },
  {
    id: 2,
    title: "第5章 传输层.pdf",
    type: "pdf",
    chapter: "第5章 传输层",
    relevance: 92,
    reason: "包含核心协议讲解",
    matchKeywords: ["TCP", "UDP", "传输层"],
  },
];

const teacherAiQuestionStore: AiTeacherQuestion[] = [
  {
    id: 1,
    student: "张三",
    avatar: "张",
    question: "TCP三次握手的第三次可以携带数据吗?",
    aiAnswer:
      "是的，TCP三次握手的第三次握手可以携带数据。\n\n在TCP三次握手过程中：\n• 第一次握手（SYN）：客户端发送SYN报文，不能携带数据\n• 第二次握手（SYN+ACK）：服务器回复SYN+ACK报文，不能携带数据\n• 第三次握手（ACK）：客户端发送ACK报文，此时连接已建立，可以携带数据\n\n这是因为前两次握手时连接尚未完全建立，而第三次握手时客户端已经确认服务器的接收能力，连接进入ESTABLISHED状态，因此可以开始传输应用层数据。",
    confidence: 45,
    confidenceLevel: "low",
    sources: [
      { name: "第4章-传输层.pdf", page: 12 },
      { name: "TCP协议详解视频.mp4", page: 0 },
    ],
    time: "10分钟前",
    status: "pending",
  },
  {
    id: 2,
    student: "李四",
    avatar: "李",
    question: "子网掩码255.255.255.0对应的CIDR表示是什么?",
    aiAnswer:
      "子网掩码255.255.255.0对应的CIDR表示为 /24。\n\n原因如下：\n• 255.255.255.0转换为二进制是：11111111.11111111.11111111.00000000\n• 连续的1有24个，因此CIDR前缀长度为24\n• 写作 /24\n\n例如：192.168.1.0/24 表示该网络有256个地址（192.168.1.0 ~ 192.168.1.255），其中可用主机地址254个（除去网络地址和广播地址）。",
    confidence: 52,
    confidenceLevel: "medium",
    sources: [{ name: "第3章-网络层.pdf", page: 15 }],
    time: "25分钟前",
    status: "pending",
  },
  {
    id: 3,
    student: "王五",
    avatar: "王",
    question: "HTTP和HTTPS的主要区别是什么?",
    aiAnswer:
      "HTTP与HTTPS的主要区别包括：\n\n1. 安全性：HTTP是明文传输，HTTPS通过TLS/SSL加密传输，防止数据被窃听和篡改\n2. 端口：HTTP默认使用80端口，HTTPS默认使用443端口\n3. 证书：HTTPS需要CA颁发的数字证书，用于身份验证\n4. 性能：HTTPS因加密解密有轻微性能开销，但现代硬件影响极小\n5. SEO：搜索引擎对HTTPS站点有更高的排名权重",
    confidence: 68,
    confidenceLevel: "medium",
    sources: [{ name: "第5章-应用层.pdf", page: 8 }],
    time: "1小时前",
    status: "pending",
  },
];

const feedbackStore: AiFeedbackItem[] = [
  {
    id: "feedback-1",
    studentName: "王五",
    conversationTitle: "子网掩码问题",
    questionContent: "255.255.255.0对应的CIDR表示是什么？",
    aiAnswer: "对应CIDR为/24。",
    reason: "希望补充更多计算过程",
    timestamp: "今天 11:20",
    status: "pending",
    courseId: "1",
  },
];

function cloneConversation(conversation: AiConversation) {
  return structuredClone(conversation);
}

function getConversationStore(role: "student" | "teacher") {
  return role === "student" ? studentConversationStore : teacherConversationStore;
}

function buildAiReply(content: string, sources: AiMessageSource[]): AiMessage {
  return {
    id: Date.now() + 1,
    role: "ai",
    content,
    time: new Date().toTimeString().slice(0, 5),
    sources,
  };
}

export async function getMockConversations(role: "student" | "teacher") {
  await waitForMockLatency();
  return getConversationStore(role).map(cloneConversation);
}

export async function getMockConversationMessages(
  role: "student" | "teacher",
  conversationId: number,
) {
  await waitForMockLatency();
  const conversation = getConversationStore(role).find((item) => item.id === conversationId);
  return structuredClone(conversation?.messages || []);
}

export async function mockCreateConversation(
  role: "student" | "teacher",
  payload: CreateConversationPayload,
) {
  await waitForMockLatency();

  const store = getConversationStore(role);
  const conversation: AiConversation = {
    id: Date.now(),
    title: payload.title?.trim() || "新会话",
    createdAt: "今天",
    lastMessage: "",
    messages: [role === "student" ? studentWelcome : teacherWelcome],
  };

  store.unshift(conversation);
  return cloneConversation(conversation);
}

export async function mockDeleteConversation(
  role: "student" | "teacher",
  conversationId: number,
) {
  await waitForMockLatency();
  const store = getConversationStore(role);
  const index = store.findIndex((item) => item.id === conversationId);
  if (index >= 0) {
    store.splice(index, 1);
  }
}

export async function mockSendMessage(
  role: "student" | "teacher",
  payload: SendMessagePayload,
) {
  await waitForMockLatency();

  const store = getConversationStore(role);
  let conversation = payload.conversationId
    ? store.find((item) => item.id === payload.conversationId)
    : undefined;

  if (!conversation) {
    conversation = {
      id: Date.now(),
      title: payload.content.slice(0, 18) || "新会话",
      createdAt: "今天",
      lastMessage: "",
      messages: [role === "student" ? studentWelcome : teacherWelcome],
    };
    store.unshift(conversation);
  }

  const userMessage: AiMessage = {
    id: Date.now(),
    role: "user",
    content: payload.content,
    time: new Date().toTimeString().slice(0, 5),
    attachments: payload.attachments,
  };

  const aiReply = buildAiReply(
    role === "student"
      ? "我已结合课程知识库生成回答草稿，后续接入真实 RAG 接口后会返回正式答案。"
      : "我已根据课程资料与学情上下文生成教学辅助建议，后续可替换为真实 AI 接口输出。",
    role === "student" ? studentAiSources : teacherAiSources,
  );

  conversation.messages.push(userMessage, aiReply);
  conversation.title = conversation.title || payload.content.slice(0, 18);
  conversation.lastMessage = aiReply.content;

  return {
    conversation: cloneConversation(conversation),
    reply: structuredClone(aiReply),
  };
}

export async function mockUploadAttachment(file: AiAttachment) {
  await waitForMockLatency();
  return structuredClone(file);
}

export async function mockLikeMessage() {
  await waitForMockLatency();
}

export async function mockDislikeMessage() {
  await waitForMockLatency();
}

export async function mockSubmitFeedback(payload: SubmitFeedbackPayload) {
  await waitForMockLatency();
  feedbackStore.unshift({
    id: crypto.randomUUID(),
    studentName: "当前学生",
    conversationTitle: `会话 #${payload.conversationId}`,
    questionContent: payload.questionContent || "",
    aiAnswer: payload.aiAnswer,
    reason: payload.reason,
    timestamp: "刚刚",
    status: "pending",
  });
}

export async function getMockTeacherAiQuestions() {
  await waitForMockLatency();
  return structuredClone(teacherAiQuestionStore);
}

export async function getMockTeacherAiQuestionDetail(questionId: number) {
  await waitForMockLatency();
  const target = teacherAiQuestionStore.find((item) => item.id === questionId);
  return structuredClone(target ?? teacherAiQuestionStore[0]);
}

export async function mockReplyAiQuestion(payload: ReplyAiQuestionPayload) {
  await waitForMockLatency();
  const target = teacherAiQuestionStore.find((item) => item.id === payload.questionId);
  if (target) {
    target.teacherReply = payload.reply;
    target.status = "replied";
  }
}

export async function mockAdoptAiAnswer(questionId: number) {
  await waitForMockLatency();
  const target = teacherAiQuestionStore.find((item) => item.id === questionId);
  if (target) {
    target.status = "adopted";
    target.teacherReply = "已采纳AI回答";
  }
}

export async function getMockFeedbackQueue() {
  await waitForMockLatency();
  return structuredClone(feedbackStore);
}

export async function mockResolveFeedback(feedbackId: string) {
  await waitForMockLatency();
  const target = feedbackStore.find((item) => item.id === feedbackId);
  if (target) {
    target.status = "resolved";
  }
}

export async function getMockRecommendations() {
  await waitForMockLatency();
  return structuredClone(recommendationStore);
}

export async function getMockMessageSources() {
  await waitForMockLatency();
  return structuredClone([...studentAiSources, ...teacherAiSources]);
}

export async function mockUpdateConversationContext(
  _payload: ConversationContextPayload,
) {
  await waitForMockLatency();
}

export async function mockUpdateConversationStyle(
  _payload: ConversationStylePayload,
) {
  await waitForMockLatency();
}

export async function mockGenerateLessonPlan(
  payload: GenerateTeacherToolPayload,
) {
  await waitForMockLatency();
  return `教案生成结果：${payload.prompt}`;
}

export async function mockGenerateExam(payload: GenerateTeacherToolPayload) {
  await waitForMockLatency();
  return `试卷生成结果：${payload.prompt}`;
}

export async function mockGenerateLearningAnalysis(
  payload: GenerateTeacherToolPayload,
) {
  await waitForMockLatency();
  return `学情分析结果：${payload.prompt}`;
}

export async function mockGenerateFlashcards(
  payload: GenerateTeacherToolPayload,
) {
  await waitForMockLatency();
  return `卡组生成结果：${payload.prompt}`;
}

export async function mockEscalateToTeacher() {
  await waitForMockLatency();
}
