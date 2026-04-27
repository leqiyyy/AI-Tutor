import { FormEvent, useState } from 'react';
import { PANEL_SEARCH_PROVIDERS, type PanelSearchResult, type PanelSearchRole } from '../lib/panel-search';

type DashboardRole = 'student' | 'teacher' | 'admin';

type PanelConfig = {
  badge: string;
  title: string;
  quote: string;
  quoteCaption: string;
  knowledgeTag: string;
  knowledgeTitle: string;
  knowledgeBody: string;
};

const PANEL_CONFIG: Record<DashboardRole, PanelConfig> = {
  student: {
    badge: 'Study Mood',
    title: '把学习留给安静而清晰的节奏',
    quote: '先完成最小的一步，学习就会开始流动。',
    quoteCaption: '今天适合先把最接近截止的一件事做完。',
    knowledgeTag: '微知识',
    knowledgeTitle: 'TCP 里的 ACK 并不只在握手里出现',
    knowledgeBody: '在连接建立后，大多数 TCP 报文段都可能携带 ACK，用来确认已经收到对方的数据。',
  },
  teacher: {
    badge: 'Teaching Mood',
    title: '好的答疑，往往来自克制而稳定的判断',
    quote: '好教学不是一次说完，而是一次次让学生真正听懂。',
    quoteCaption: '今天适合先看重复率最高的问题，再统一回应。',
    knowledgeTag: '教学摘记',
    knowledgeTitle: '低置信回答比高频问题更值得优先看一眼',
    knowledgeBody: '高频问题常常能被统一处理，而低置信回答更容易影响学生信任感，适合先人工复核。',
  },
  admin: {
    badge: 'Ops Mood',
    title: '稳定感来自很多细小问题被及时处理',
    quote: '真正高级的系统体验，是大多数问题在用户察觉前就被处理掉。',
    quoteCaption: '今天适合先看影响链路稳定的问题。',
    knowledgeTag: '系统笔记',
    knowledgeTitle: '知识库异常通常先看源文件格式与解析日志',
    knowledgeBody: '很多索引异常不是模型本身造成的，而是文件结构、编码或解析流程中的前置问题。',
  },
};

interface ProductSidePanelProps {
  role: DashboardRole;
}

export default function ProductSidePanel({ role }: ProductSidePanelProps) {
  const config = PANEL_CONFIG[role];
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PanelSearchResult[]>([]);
  const [activeResultId, setActiveResultId] = useState<string>('');
  const [isSearching, setIsSearching] = useState(false);

  const currentProvider = PANEL_SEARCH_PROVIDERS[0];
  const activeResult = results.find((item) => item.id === activeResultId) ?? results[0] ?? null;

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      setResults([]);
      setActiveResultId('');
      return;
    }

    setIsSearching(true);
    const nextResults = await currentProvider.search(normalized, role as PanelSearchRole);
    setResults(nextResults);
    setActiveResultId(nextResults[0]?.id ?? '');
    setIsSearching(false);
  };

  return (
    <aside className={`soft-product-panel soft-product-panel--${role}`}>
      <div className="soft-product-panel__scroll">
        <section className="soft-product-panel__hero">
          <div className="soft-product-panel__badge">{config.badge}</div>
          <h2 className="soft-product-panel__title">{config.title}</h2>

          <div className="soft-product-panel__scene" aria-hidden="true">
            <div className="soft-product-panel__cloud soft-product-panel__cloud--one"></div>
            <div className="soft-product-panel__cloud soft-product-panel__cloud--two"></div>
            <div className="soft-product-panel__bubble soft-product-panel__bubble--book">
              <i className="ri-book-open-line"></i>
            </div>
            <div className="soft-product-panel__bubble soft-product-panel__bubble--rocket">
              <i className="ri-rocket-line"></i>
            </div>
            <div className="soft-product-panel__bubble soft-product-panel__bubble--planet">
              <i className="ri-planet-line"></i>
            </div>
          </div>
        </section>

        <section className="soft-product-panel__panel-card">
          <div className="soft-product-panel__section-label">今日一句</div>
          <p className="soft-product-panel__quote">“{config.quote}”</p>
          <p className="soft-product-panel__caption">{config.quoteCaption}</p>
        </section>

        <section className="soft-product-panel__panel-card soft-product-panel__panel-card--search">
          <form onSubmit={handleSearch} className="soft-product-panel__search-form">
            <div className="soft-product-panel__search-box">
              <i className="ri-search-line"></i>
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={currentProvider.placeholder}
                className="soft-product-panel__search-input"
              />
            </div>
            <button type="submit" className="soft-product-panel__search-button">
              检索
            </button>
          </form>

          {query.trim() !== '' && (
            <div className="soft-product-panel__search-results">
              <div className="soft-product-panel__result-list">
                {isSearching ? (
                  <div className="soft-product-panel__search-empty">正在检索中…</div>
                ) : (
                  results.map((result) => (
                    <button
                      key={result.id}
                      type="button"
                      onClick={() => setActiveResultId(result.id)}
                      className={`soft-product-panel__result-item ${
                        activeResult?.id === result.id ? 'soft-product-panel__result-item--active' : ''
                      }`}
                    >
                      <div className="soft-product-panel__result-title">{result.title}</div>
                      <div className="soft-product-panel__result-meta">{result.meta}</div>
                    </button>
                  ))
                )}
              </div>

              {activeResult && !isSearching && (
                <div className="soft-product-panel__result-preview">
                  <div className="soft-product-panel__result-preview-title">{activeResult.title}</div>
                  <p className="soft-product-panel__result-preview-body">{activeResult.excerpt}</p>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="soft-product-panel__panel-card soft-product-panel__panel-card--knowledge">
          <div className="soft-product-panel__knowledge-tag">{config.knowledgeTag}</div>
          <div className="soft-product-panel__knowledge-title">{config.knowledgeTitle}</div>
          <p className="soft-product-panel__knowledge-body">{config.knowledgeBody}</p>
        </section>
      </div>
    </aside>
  );
}
