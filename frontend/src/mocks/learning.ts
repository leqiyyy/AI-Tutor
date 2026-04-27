import type {
  CreateFlashcardDeckRequest,
  CreateMistakeRequest,
  FlashcardDeck,
  FlashcardDecksData,
  LearningOverviewData,
  LearningMistake,
  LearningMistakesData,
} from "@/types/learning";

// 用途: MyLearning.tsx 与学生课程页错题/闪卡/学习概览联调
// 页面来源: student-course/components/MyLearning.tsx、student-course/page.tsx
// 未来接口归属: learningService.getMistakes/getFlashcardDecks/getLearningOverview/exportLearningData 等

const mockMistakes: LearningMistake[] = [
  {
    id: 1,
    question: "TCP三次握手过程中，第二次握手发送的标志位是？",
    chapter: "第5章 传输层",
    wrongCount: 2,
    myAnswer: "SYN",
    correctAnswer: "SYN+ACK",
    analysis: "第二次握手时，服务器需要同时发送SYN和ACK标志位，表示同意建立连接并确认收到客户端的SYN。",
    addTime: "2024-03-10",
    lastPracticeTime: "2024-03-15",
    mastered: false,
  },
  {
    id: 2,
    question: "红黑树的左旋和右旋操作具体是如何实现的？",
    chapter: "第7章 树",
    wrongCount: 1,
    myAnswer: "将节点向左移动",
    correctAnswer: "左旋是将节点的右子节点提升为新的根节点，原节点成为新根的左子节点；右旋相反。",
    analysis: "旋转操作是红黑树保持平衡的关键。左旋和右旋是对称的操作，需要正确处理节点之间的指针关系。",
    addTime: "2024-03-12",
    lastPracticeTime: "2024-03-16",
    mastered: false,
  },
  {
    id: 3,
    question: "进程调度算法中，时间片轮转的优缺点是？",
    chapter: "第4章 进程管理",
    wrongCount: 1,
    myAnswer: "优点是公平，缺点是效率低",
    correctAnswer: "优点：公平性好，响应时间短；缺点：上下文切换开销大，时间片大小难以确定。",
    analysis: "时间片轮转算法是一种抢占式调度算法，需要权衡公平性和效率。时间片太小会导致频繁切换，太大则退化为先来先服务。",
    addTime: "2024-03-08",
    lastPracticeTime: "2024-03-14",
    mastered: true,
  },
];

const mockDecks: FlashcardDeck[] = [
  {
    id: 1,
    name: "第5章 传输层",
    cards: 45,
    mastered: 32,
    learning: 10,
    new: 3,
    nextReview: "今天",
    cardList: [
      {
        front: "TCP三次握手的三个步骤是什么？",
        back: "1. SYN：客户端发送SYN报文\n2. SYN+ACK：服务器回复SYN+ACK报文\n3. ACK：客户端发送ACK报文，连接建立",
      },
      {
        front: "TCP拥塞控制的四个算法是什么？",
        back: "1. 慢启动（Slow Start）\n2. 拥塞避免（Congestion Avoidance）\n3. 快速重传（Fast Retransmit）\n4. 快速恢复（Fast Recovery）",
      },
      {
        front: "UDP协议的特点有哪些？",
        back: "1. 无连接\n2. 不可靠传输\n3. 面向报文\n4. 无拥塞控制\n5. 支持一对一、一对多、多对多通信",
      },
    ],
  },
  {
    id: 2,
    name: "第4章 网络层",
    cards: 38,
    mastered: 28,
    learning: 8,
    new: 2,
    nextReview: "明天",
    cardList: [
      {
        front: "IP地址分为哪几类？",
        back: "A类：1.0.0.0 ~ 126.255.255.255\nB类：128.0.0.0 ~ 191.255.255.255\nC类：192.0.0.0 ~ 223.255.255.255\nD类：224.0.0.0 ~ 239.255.255.255（组播）\nE类：240.0.0.0 ~ 255.255.255.255（保留）",
      },
      {
        front: "子网掩码的作用是什么？",
        back: "子网掩码用于将IP地址划分为网络部分和主机部分，通过与IP地址进行按位与运算，可以得到网络地址。",
      },
    ],
  },
  {
    id: 3,
    name: "第3章 数据链路层",
    cards: 42,
    mastered: 35,
    learning: 5,
    new: 2,
    nextReview: "2天后",
    cardList: [],
  },
  {
    id: 4,
    name: "TCP协议专题",
    cards: 28,
    mastered: 20,
    learning: 6,
    new: 2,
    nextReview: "今天",
    cardList: [],
  },
  {
    id: 5,
    name: "路由算法",
    cards: 25,
    mastered: 18,
    learning: 5,
    new: 2,
    nextReview: "3天后",
    cardList: [],
  },
  {
    id: 6,
    name: "我的自定义卡组",
    cards: 15,
    mastered: 8,
    learning: 5,
    new: 2,
    nextReview: "今天",
    cardList: [],
  },
];

const mockLearningOverview: LearningOverviewData = {
  summaryCards: [
    {
      label: "本周学习时长",
      value: "18.5h",
      sub: "目标 20h",
      icon: "ri-time-line",
      color: "teal",
      progress: 92,
    },
    {
      label: "作业完成率",
      value: "92%",
      sub: "12 / 13 完成",
      icon: "ri-task-line",
      color: "green",
      progress: 92,
    },
    {
      label: "AI提问次数",
      value: "47",
      sub: "本月累计 189次",
      icon: "ri-robot-line",
      color: "sky",
      progress: 63,
    },
    {
      label: "课程综合进度",
      value: "75%",
      sub: "稳步提升中",
      icon: "ri-bar-chart-2-line",
      color: "violet",
      progress: 75,
    },
  ],
  radarData: [
    { label: "物理层", score: 88, fullScore: 100 },
    { label: "数据链路层", score: 76, fullScore: 100 },
    { label: "网络层", score: 82, fullScore: 100 },
    { label: "传输层", score: 71, fullScore: 100 },
    { label: "应用层", score: 65, fullScore: 100 },
    { label: "协议分析", score: 79, fullScore: 100 },
  ],
  keywordData: [
    { word: "TCP", count: 28 },
    { word: "三次握手", count: 22 },
    { word: "IP地址", count: 19 },
    { word: "拥塞控制", count: 16 },
    { word: "UDP", count: 14 },
    { word: "路由算法", count: 13 },
    { word: "DNS", count: 11 },
    { word: "HTTP", count: 10 },
    { word: "子网划分", count: 9 },
    { word: "滑动窗口", count: 8 },
    { word: "ARP协议", count: 7 },
    { word: "四次挥手", count: 7 },
    { word: "OSI模型", count: 6 },
    { word: "以太网", count: 6 },
    { word: "ICMP", count: 5 },
    { word: "数据报", count: 5 },
    { word: "NAT", count: 4 },
    { word: "流量控制", count: 4 },
    { word: "FTP", count: 3 },
    { word: "DHCP", count: 3 },
    { word: "SMTP", count: 3 },
    { word: "帧结构", count: 2 },
    { word: "CSMA", count: 2 },
    { word: "差错控制", count: 2 },
  ],
  weekHours: [
    { day: "周一", hours: 2.5, date: "04/04" },
    { day: "周二", hours: 1.8, date: "04/05" },
    { day: "周三", hours: 3.2, date: "04/06" },
    { day: "周四", hours: 2.0, date: "04/07" },
    { day: "周五", hours: 3.8, date: "04/08" },
    { day: "周六", hours: 4.5, date: "04/09" },
    { day: "周日", hours: 0.7, date: "04/10" },
  ],
  chapterProgress: [
    { name: "第1章 计算机网络概述", progress: 100, status: "done" },
    { name: "第2章 物理层", progress: 100, status: "done" },
    { name: "第3章 数据链路层", progress: 92, status: "done" },
    { name: "第4章 网络层", progress: 84, status: "active" },
    { name: "第5章 传输层", progress: 71, status: "active" },
    { name: "第6章 应用层", progress: 35, status: "pending" },
  ],
};

export function getMockMistakes(): LearningMistakesData {
  return {
    mistakes: mockMistakes.map((mistake) => ({ ...mistake })),
  };
}

export function getMockFlashcardDecks(): FlashcardDecksData {
  return {
    decks: mockDecks.map((deck) => ({
      ...deck,
      cardList: deck.cardList.map((card) => ({ ...card })),
    })),
  };
}

export function mockCreateMistake(
  payload: CreateMistakeRequest,
): LearningMistake {
  const today = new Date().toISOString().split("T")[0];

  return {
    id: Date.now(),
    question: payload.question,
    chapter: payload.chapter,
    wrongCount: 1,
    myAnswer: payload.myAnswer,
    correctAnswer: payload.correctAnswer,
    analysis: payload.analysis,
    addTime: today,
    lastPracticeTime: today,
    mastered: false,
  };
}

export function mockCreateFlashcardDeck(
  payload: CreateFlashcardDeckRequest,
): FlashcardDeck {
  return {
    id: Date.now(),
    name: payload.name,
    cards: payload.cards.length,
    mastered: 0,
    learning: 0,
    new: payload.cards.length,
    nextReview: "今天",
    cardList: payload.cards.map((card) => ({ ...card })),
  };
}

export function getMockLearningOverview(): LearningOverviewData {
  return {
    summaryCards: mockLearningOverview.summaryCards.map((item) => ({ ...item })),
    radarData: mockLearningOverview.radarData.map((item) => ({ ...item })),
    keywordData: mockLearningOverview.keywordData.map((item) => ({ ...item })),
    weekHours: mockLearningOverview.weekHours.map((item) => ({ ...item })),
    chapterProgress: mockLearningOverview.chapterProgress.map((item) => ({
      ...item,
    })),
  };
}
