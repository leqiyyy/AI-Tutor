export type PanelSearchRole = 'student' | 'teacher' | 'admin';

export type PanelSearchSource = 'local' | 'learning' | 'browser';

export interface PanelSearchResult {
  id: string;
  title: string;
  excerpt: string;
  meta: string;
  source: PanelSearchSource;
}

export interface PanelSearchProvider {
  key: PanelSearchSource;
  placeholder: string;
  search: (query: string, role: PanelSearchRole) => Promise<PanelSearchResult[]>;
}

type SearchEntry = {
  id: string;
  roles: PanelSearchRole[];
  title: string;
  body: string;
  meta: string;
  tags: string[];
};

const LOCAL_SEARCH_DATA: SearchEntry[] = [
  {
    id: 'student-tcp-ack',
    roles: ['student'],
    title: 'TCP ACK 的常见使用场景',
    body: 'ACK 不只用于三次握手，在连接建立后，大多数 TCP 报文段也会携带 ACK 字段来确认数据接收状态。',
    meta: '课程知识摘要',
    tags: ['tcp', 'ack', '传输层', '网络'],
  },
  {
    id: 'student-review-rhythm',
    roles: ['student'],
    title: '高效复习的最小节奏',
    body: '在学习任务较多时，优先完成最接近截止的一项，再对薄弱点做 10 到 15 分钟的集中复习，通常比一次铺开更有效。',
    meta: '学习方法提示',
    tags: ['复习', '节奏', '学习方法'],
  },
  {
    id: 'teacher-low-confidence',
    roles: ['teacher'],
    title: '为什么优先处理低置信回答',
    body: '低置信回答可能直接影响学生对 AI 助教的信任感。先做人工复核，通常比先追高频问题更能稳定体验。',
    meta: '教学运营笔记',
    tags: ['答疑', '低置信', 'ai', '教学'],
  },
  {
    id: 'teacher-qa-batch',
    roles: ['teacher'],
    title: '集中答疑的组织方式',
    body: '把重复问题整理成统一答疑内容，再补充个别差异点，可以降低重复劳动，也更便于学生回看。',
    meta: '教学策略卡片',
    tags: ['答疑', '课堂', '组织'],
  },
  {
    id: 'admin-kb-incident',
    roles: ['admin'],
    title: '知识库异常的优先排查路径',
    body: '多数解析异常首先要检查源文件格式、编码与分段逻辑，其次再排查索引流程和服务状态。',
    meta: '运维巡检摘要',
    tags: ['知识库', '异常', '解析', '运维'],
  },
  {
    id: 'admin-review-priority',
    roles: ['admin'],
    title: '审核队列的优先级判断',
    body: '优先处理会阻塞注册、授课或资料访问链路的问题，再清理低风险积压项，通常能更快恢复整体体验。',
    meta: '系统管理提示',
    tags: ['审核', '优先级', '系统'],
  },
];

function scoreEntry(entry: SearchEntry, query: string) {
  const normalized = query.toLowerCase().trim();
  if (!normalized) return 0;

  let score = 0;
  if (entry.title.toLowerCase().includes(normalized)) score += 6;
  if (entry.body.toLowerCase().includes(normalized)) score += 3;
  if (entry.tags.some((tag) => tag.toLowerCase().includes(normalized))) score += 4;

  const terms = normalized.split(/\s+/).filter(Boolean);
  for (const term of terms) {
    if (entry.title.toLowerCase().includes(term)) score += 2;
    if (entry.body.toLowerCase().includes(term)) score += 1;
    if (entry.tags.some((tag) => tag.toLowerCase().includes(term))) score += 2;
  }

  return score;
}

async function searchLocal(query: string, role: PanelSearchRole): Promise<PanelSearchResult[]> {
  await new Promise((resolve) => setTimeout(resolve, 180));

  const matches = LOCAL_SEARCH_DATA
    .filter((entry) => entry.roles.includes(role))
    .map((entry) => ({ entry, score: scoreEntry(entry, query) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map(({ entry }) => ({
      id: entry.id,
      title: entry.title,
      excerpt: entry.body,
      meta: entry.meta,
      source: 'local' as const,
    }));

  if (matches.length > 0) return matches;

  return [
    {
      id: `local-empty-${role}`,
      title: '暂时没有匹配内容',
      excerpt: '可以尝试更短的关键词，例如“TCP”“答疑”“审核”，后续也可接入外部学习平台或浏览器搜索源。',
      meta: '本地检索',
      source: 'local',
    },
  ];
}

function buildIntegrationPlaceholder(
  source: PanelSearchSource,
  title: string,
  excerpt: string,
): PanelSearchResult[] {
  return [
    {
      id: `${source}-placeholder`,
      title,
      excerpt,
      meta: '待接入 provider',
      source,
    },
  ];
}

async function searchLearningPlatform(query: string): Promise<PanelSearchResult[]> {
  await new Promise((resolve) => setTimeout(resolve, 160));

  return buildIntegrationPlaceholder(
    'learning',
    '学习平台检索接口已预留',
    `当前关键词“${query}”会在接入后发送到外部学习平台。你后续只需要把 provider 的 search 函数替换成真实 API 请求即可。`,
  );
}

async function searchBrowserBridge(query: string): Promise<PanelSearchResult[]> {
  await new Promise((resolve) => setTimeout(resolve, 160));

  return buildIntegrationPlaceholder(
    'browser',
    '浏览器检索接口已预留',
    `当前关键词“${query}”后续可转发到浏览器 API 或扩展桥接层，再把结果回填到面板中做简易查看。`,
  );
}

export const PANEL_SEARCH_PROVIDERS: PanelSearchProvider[] = [
  {
    key: 'local',
    placeholder: '检索知识点、短句或后续接入内容',
    search: searchLocal,
  },
  {
    key: 'learning',
    placeholder: '预留：后续接入外部学习平台',
    search: (query) => searchLearningPlatform(query),
  },
  {
    key: 'browser',
    placeholder: '预留：后续接入浏览器 API',
    search: (query) => searchBrowserBridge(query),
  },
];
