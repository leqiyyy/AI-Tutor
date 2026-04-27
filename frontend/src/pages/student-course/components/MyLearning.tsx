import { useState, useEffect, useRef, useCallback } from 'react';
import { learningService } from '@/services/learning';
import type { LearningOverviewData } from '@/types/learning';

interface WordItem {
  word: string;
  count: number;
  color: string;
  fontSize: number;
  x: number;
  y: number;
  rotation: number;
  width: number;
  height: number;
}

const EMPTY_LEARNING_OVERVIEW: LearningOverviewData = {
  summaryCards: [],
  radarData: [],
  keywordData: [],
  weekHours: [],
  chapterProgress: [],
};

const PALETTE = ['#0d9488', '#0891b2', '#0284c7', '#059669', '#7c3aed', '#be123c', '#d97706', '#16a34a'];

function hexPoints(cx: number, cy: number, r: number, n: number): [number, number][] {
  return Array.from({ length: n }, (_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)] as [number, number];
  });
}

function dataPoints(cx: number, cy: number, maxR: number, scores: number[], n: number): [number, number][] {
  return scores.map((score, i) => {
    const ratio = score / 100;
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + maxR * ratio * Math.cos(angle), cy + maxR * ratio * Math.sin(angle)] as [number, number];
  });
}

function pointsToSVGStr(pts: [number, number][]): string {
  return pts.map(([x, y]) => `${x},${y}`).join(' ');
}

function buildWordCloud(words: { word: string; count: number }[], width: number, height: number): WordItem[] {
  if (words.length === 0) return [];

  const maxCount = Math.max(...words.map(w => w.count));
  const minCount = Math.min(...words.map(w => w.count));
  const placed: WordItem[] = [];

  const toFontSize = (count: number) => {
    const t = (count - minCount) / Math.max(1, maxCount - minCount);
    return Math.round(11 + t * 22);
  };

  const cx = width / 2;
  const cy = height / 2;

  const overlaps = (item: WordItem): boolean => {
    for (const p of placed) {
      const dx = Math.abs(item.x - p.x);
      const dy = Math.abs(item.y - p.y);
      const hw = (item.width + p.width) / 2 + 4;
      const hh = (item.height + p.height) / 2 + 4;
      if (dx < hw && dy < hh) return true;
    }
    return false;
  };

  for (let wi = 0; wi < words.length; wi++) {
    const { word, count } = words[wi];
    const fontSize = toFontSize(count);
    const charW = fontSize * 0.62;
    const ww = word.length * charW;
    const wh = fontSize * 1.2;
    const rotation = wi % 5 === 0 ? -30 : wi % 7 === 0 ? 30 : 0;
    const color = PALETTE[wi % PALETTE.length];

    let placed_flag = false;
    for (let r = 0; r < 200; r += 2) {
      const totalAngleSteps = Math.max(1, Math.round((2 * Math.PI * Math.max(r, 1)) / 20));
      for (let s = 0; s < totalAngleSteps; s++) {
        const angle = (2 * Math.PI * s) / totalAngleSteps + r * 0.15;
        const x = cx + r * Math.cos(angle);
        const y = cy + r * Math.sin(angle);
        const candidate: WordItem = { word, count, color, fontSize, x, y, rotation, width: ww, height: wh };
        if (
          x - ww / 2 > 4 && x + ww / 2 < width - 4 &&
          y - wh / 2 > 4 && y + wh / 2 < height - 4 &&
          !overlaps(candidate)
        ) {
          placed.push(candidate);
          placed_flag = true;
          break;
        }
      }
      if (placed_flag) break;
    }
  }

  return placed;
}

interface MyLearningProps {
  courseId: string;
}

export default function MyLearning({ courseId }: MyLearningProps) {
  const [overview, setOverview] = useState<LearningOverviewData>(EMPTY_LEARNING_OVERVIEW);
  const [cloudWords, setCloudWords] = useState<WordItem[]>([]);
  const [cloudReady, setCloudReady] = useState(false);
  const cloudRef = useRef<SVGSVGElement>(null);
  const [cloudSize, setCloudSize] = useState({ width: 560, height: 240 });
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [showWeeklyModal, setShowWeeklyModal] = useState(false);
  const [showMonthlyModal, setShowMonthlyModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState('csv');
  const [exportFields, setExportFields] = useState({ studyTime: true, homework: true, aiQuestions: true, attendance: true, grades: true });
  const { summaryCards, radarData, keywordData, weekHours, chapterProgress } = overview;

  const rebuildCloud = useCallback((w: number, h: number) => {
    setCloudReady(false);
    const words = buildWordCloud(keywordData, w, h);
    setCloudWords(words);
    setTimeout(() => setCloudReady(true), 50);
  }, [keywordData]);

  useEffect(() => {
    let mounted = true;

    learningService
      .getLearningOverview(courseId)
      .then((data) => {
        if (mounted) setOverview(data);
      })
      .catch(() => {
        if (mounted) setOverview(EMPTY_LEARNING_OVERVIEW);
      });

    return () => {
      mounted = false;
    };
  }, [courseId]);

  useEffect(() => {
    const measure = () => {
      if (cloudRef.current) {
        const rect = cloudRef.current.parentElement?.getBoundingClientRect();
        if (rect && rect.width > 0) {
          const w = rect.width - 2;
          const h = Math.max(220, Math.round(w * 0.42));
          setCloudSize({ width: w, height: h });
          rebuildCloud(w, h);
        }
      }
    };
    measure();
    const obs = new ResizeObserver(measure);
    if (cloudRef.current?.parentElement) obs.observe(cloudRef.current.parentElement);
    return () => obs.disconnect();
  }, [rebuildCloud]);

  // Radar SVG params — centered, larger
  const cx = 180;
  const cy = 180;
  const maxR = 130;
  const n = radarData.length;
  const levels = [0.25, 0.5, 0.75, 1.0];

  const scores = radarData.map(d => d.score);
  const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const dataPts = dataPoints(cx, cy, maxR, scores, n);
  const weakItems = radarData.filter(d => d.score < 75).sort((a, b) => a.score - b.score);
  const maxHours = Math.max(1, ...weekHours.map((item) => item.hours));
  const weekTotalHours = weekHours.reduce((sum, item) => sum + item.hours, 0);
  const dailyAverageHours = weekHours.length > 0 ? weekTotalHours / weekHours.length : 0;
  const completedChapterCount = chapterProgress.filter((item) => item.progress >= 90).length;

  const getLabelPos = (i: number): [number, number] => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const labelR = maxR + 26;
    return [cx + labelR * Math.cos(angle), cy + labelR * Math.sin(angle)];
  };

  const handleExportLearningData = async () => {
    await learningService.exportLearningData(courseId, {
      format: exportFormat,
      fields: exportFields,
    });
    setShowExportModal(false);
    alert('学习数据导出任务已提交');
  };

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">我的学习</h1>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowWeeklyModal(true)} className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer whitespace-nowrap">
            <i className="ri-file-text-line mr-1"></i>周报
          </button>
          <button onClick={() => setShowMonthlyModal(true)} className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer whitespace-nowrap">
            <i className="ri-file-chart-line mr-1"></i>月报
          </button>
          <button onClick={() => setShowExportModal(true)} className="px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 border border-teal-200 rounded-lg hover:bg-teal-100 cursor-pointer whitespace-nowrap">
            <i className="ri-download-line mr-1"></i>导出
          </button>
        </div>
      </div>

      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        {summaryCards.map((item, i) => (
          <div key={i} className="bg-white rounded-xl p-4 border border-gray-200">
            <div className="flex items-start justify-between mb-3">
              <div className={`w-9 h-9 flex items-center justify-center rounded-lg bg-${item.color}-50`}>
                <i className={`${item.icon} text-${item.color}-600 text-base`}></i>
              </div>
              <span className="text-xs text-gray-400">{item.sub}</span>
            </div>
            <div className={`text-2xl font-bold text-${item.color}-600 mb-1`}>{item.value}</div>
            <div className="text-xs text-gray-500 mb-2">{item.label}</div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full bg-${item.color}-400 rounded-full transition-all duration-700`}
                style={{ width: `${item.progress}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      {/* 知识掌握雷达图（居中版） + 本周学习柱状图 */}
      <div className="grid grid-cols-5 gap-5">
        {/* 知识掌握雷达图 */}
        <div className="col-span-3 bg-white rounded-xl p-6 border border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="text-sm font-semibold text-gray-900">知识掌握雷达图</h2>
              <p className="text-xs text-gray-400 mt-0.5">综合评分基于作业、测验及AI对话</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-gray-300 rounded"></span> 满分线
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-teal-500 rounded"></span> 我的水平
              </span>
            </div>
          </div>

          {/* 雷达图居中展示 */}
          <div className="flex flex-col items-center">
            <svg viewBox="0 0 360 360" width="300" height="300">
              {/* 背景网格 */}
              {levels.map((lvl, li) => {
                const pts = hexPoints(cx, cy, maxR * lvl, n);
                return (
                  <polygon
                    key={li}
                    points={pointsToSVGStr(pts)}
                    fill={li === levels.length - 1 ? '#f0fdfa' : 'none'}
                    stroke={li === levels.length - 1 ? '#99f6e4' : '#e5e7eb'}
                    strokeWidth={li === levels.length - 1 ? 1.5 : 1}
                  />
                );
              })}

              {/* 轴线 */}
              {Array.from({ length: n }, (_, i) => {
                const [ex, ey] = hexPoints(cx, cy, maxR, n)[i];
                return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="#d1fae5" strokeWidth="1" />;
              })}

              {/* 刻度值 */}
              {levels.map((lvl, li) => (
                <text key={li} x={cx + 5} y={cy - maxR * lvl + 4} fontSize="9" fill="#9ca3af" textAnchor="start">
                  {Math.round(lvl * 100)}
                </text>
              ))}

              {/* 数据填充区域 */}
              <polygon
                points={pointsToSVGStr(dataPts)}
                fill="#14b8a6"
                fillOpacity="0.22"
                stroke="#14b8a6"
                strokeWidth="2"
                strokeLinejoin="round"
              />

              {/* 数据点 */}
              {dataPts.map(([px, py], i) => (
                <circle key={i} cx={px} cy={py} r="5" fill="#14b8a6" stroke="white" strokeWidth="2" />
              ))}

              {/* 坐标标签 */}
              {radarData.map((d, i) => {
                const [lx, ly] = getLabelPos(i);
                const anchor = lx < cx - 5 ? 'end' : lx > cx + 5 ? 'start' : 'middle';
                return (
                  <g key={i}>
                    <text x={lx} y={ly - 4} textAnchor={anchor} fontSize="11" fontWeight="600" fill="#374151">
                      {d.label}
                    </text>
                    <text x={lx} y={ly + 10} textAnchor={anchor} fontSize="10" fill="#14b8a6" fontWeight="700">
                      {d.score}
                    </text>
                  </g>
                );
              })}

              {/* 中心综合分 */}
              <text x={cx} y={cy - 8} textAnchor="middle" fontSize="22" fontWeight="700" fill="#0d9488">{avgScore}</text>
              <text x={cx} y={cy + 10} textAnchor="middle" fontSize="9" fill="#9ca3af">综合得分</text>
            </svg>

            {/* 底部弱项提示 */}
            {weakItems.length > 0 && (
              <div className="mt-2 w-full px-2 py-2.5 bg-amber-50 rounded-lg border border-amber-100 flex items-start gap-2">
                <i className="ri-alert-line text-amber-500 text-sm flex-shrink-0 mt-0.5"></i>
                <div className="text-xs text-amber-700">
                  <span className="font-medium">待加强：</span>
                  {weakItems.map((d, i) => (
                    <span key={i}>{d.label}（{d.score}分）{i < weakItems.length - 1 ? ' · ' : ''}</span>
                  ))}
                  <span className="ml-1 text-amber-500">建议重点复习</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 本周学习时长柱状图 */}
        <div className="col-span-2 bg-white rounded-xl p-5 border border-gray-200">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">本周每日学习时长</h2>
          <p className="text-xs text-gray-400 mb-4">单位：小时 · 合计 {weekTotalHours.toFixed(1)}h</p>

          <div className="flex items-end justify-between gap-2 h-36">
            {weekHours.map((d, i) => {
              const heightPct = (d.hours / maxHours) * 100;
              const isToday = i === weekHours.length - 1;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
                  <div className="text-xs text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    {d.hours}h
                  </div>
                  <div className="w-full relative flex items-end" style={{ height: '100px' }}>
                    <div
                      className={`w-full rounded-t-md transition-all duration-500 ${isToday ? 'bg-teal-500' : 'bg-teal-200 group-hover:bg-teal-400'}`}
                      style={{ height: `${heightPct}%` }}
                    ></div>
                  </div>
                  <div className={`text-xs font-medium ${isToday ? 'text-teal-600' : 'text-gray-500'}`}>{d.day}</div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="p-3 bg-teal-50 rounded-lg">
              <div className="text-base font-bold text-teal-600">{dailyAverageHours.toFixed(2)}h</div>
              <div className="text-xs text-gray-500 mt-0.5">日均学习</div>
            </div>
            <div className="p-3 bg-green-50 rounded-lg">
              <div className="text-base font-bold text-green-600">+23%</div>
              <div className="text-xs text-gray-500 mt-0.5">较上周提升</div>
            </div>
          </div>
        </div>
      </div>

      {/* 课程章节进度 */}
      <div className="bg-white rounded-xl p-5 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-900">章节学习进度</h2>
          <span className="text-xs text-gray-400">{chapterProgress.length}章 · {completedChapterCount}章已基本完成</span>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-3">
          {chapterProgress.map((ch, i) => (
            <div key={i}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    ch.status === 'done' ? 'bg-green-500' : ch.status === 'active' ? 'bg-teal-500' : 'bg-gray-300'
                  }`}></span>
                  <span className="text-xs text-gray-700">{ch.name}</span>
                </div>
                <span className={`text-xs font-semibold ${
                  ch.progress === 100 ? 'text-green-600' : ch.progress >= 70 ? 'text-teal-600' : 'text-amber-500'
                }`}>{ch.progress}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    ch.progress === 100 ? 'bg-green-400' : ch.progress >= 70 ? 'bg-teal-400' : 'bg-amber-300'
                  }`}
                  style={{ width: `${ch.progress}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 提问关键词词云 */}
      <div className="bg-white rounded-xl p-5 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">提问历史词云</h2>
            <p className="text-xs text-gray-400 mt-0.5">基于 {keywordData.reduce((s, w) => s + w.count, 0)} 次 AI 对话 · 词越大提问越多</p>
          </div>
          <div className="flex flex-wrap gap-1 max-w-xs justify-end">
            {keywordData.slice(0, 5).map((kw, i) => (
              <span key={i} className="px-2 py-0.5 text-xs rounded-full bg-teal-50 text-teal-600 border border-teal-100">
                {kw.word} ×{kw.count}
              </span>
            ))}
          </div>
        </div>

        <div className="relative overflow-hidden rounded-lg bg-gradient-to-br from-slate-50 to-teal-50 border border-gray-100">
          <svg
            ref={cloudRef}
            width="100%"
            height={cloudSize.height}
            viewBox={`0 0 ${cloudSize.width} ${cloudSize.height}`}
            className={`transition-opacity duration-300 ${cloudReady ? 'opacity-100' : 'opacity-0'}`}
          >
            {cloudWords.map((item, i) => (
              <text
                key={i}
                x={item.x}
                y={item.y}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={item.fontSize}
                fontWeight={item.count > 15 ? 700 : item.count > 8 ? 600 : 500}
                fill={item.color}
                opacity={hoveredWord === null ? 0.85 : hoveredWord === item.word ? 1 : 0.3}
                transform={item.rotation !== 0 ? `rotate(${item.rotation}, ${item.x}, ${item.y})` : undefined}
                className="cursor-pointer transition-opacity duration-200 select-none"
                onMouseEnter={() => setHoveredWord(item.word)}
                onMouseLeave={() => setHoveredWord(null)}
                style={{ fontFamily: "'Noto Sans SC', sans-serif" }}
              >
                {item.word}
              </text>
            ))}
            {!cloudReady && (
              <text x={cloudSize.width / 2} y={cloudSize.height / 2} textAnchor="middle" fill="#9ca3af" fontSize="13">
                词云生成中...
              </text>
            )}
          </svg>

          {hoveredWord && (() => {
            const kw = keywordData.find(k => k.word === hoveredWord);
            return kw ? (
              <div className="absolute bottom-3 right-3 bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs pointer-events-none">
                <span className="font-semibold text-gray-900">{kw.word}</span>
                <span className="text-gray-500 ml-2">提问 {kw.count} 次</span>
              </div>
            ) : null;
          })()}
        </div>
      </div>

      {/* 周报弹窗 */}
      {showWeeklyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
              <h2 className="text-base font-semibold text-gray-900">学习周报 · 2026.04.04 - 04.10</h2>
              <button onClick={() => setShowWeeklyModal(false)} className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                <i className="ri-close-line text-xl"></i>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: '学习时长', value: '18.5h', color: 'teal' },
                  { label: '作业完成', value: '92%', color: 'green' },
                  { label: 'AI提问', value: '47次', color: 'sky' },
                  { label: '闪卡复习', value: '156张', color: 'violet' },
                ].map((s, i) => (
                  <div key={i} className={`p-3 bg-${s.color}-50 rounded-lg border border-${s.color}-100 text-center`}>
                    <div className={`text-xl font-bold text-${s.color}-600`}>{s.value}</div>
                    <div className="text-xs text-gray-500 mt-1">{s.label}</div>
                  </div>
                ))}
              </div>
              <div className="p-4 bg-amber-50 rounded-lg border border-amber-100">
                <div className="text-xs font-semibold text-amber-700 mb-2">薄弱知识点</div>
                <div className="space-y-1 text-xs text-gray-700">
                  <div>• TCP拥塞控制：建议重温慢启动与拥塞避免的临界条件</div>
                  <div>• 子网划分：CIDR 表示法练习不足，建议多做计算题</div>
                </div>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                <div className="text-xs font-semibold text-sky-700 mb-2">AI 学习建议</div>
                <div className="space-y-1 text-xs text-gray-700">
                  <div>• 本周时长充足，但分布不均，建议工作日保持 2h 以上</div>
                  <div>• 应用层（HTTP、DNS）是下周重点，提前预习效果更佳</div>
                  <div>• 闪卡复习习惯良好，继续保持每日打卡</div>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2 flex-shrink-0">
              <button onClick={() => setShowWeeklyModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap">
                <i className="ri-download-line mr-1"></i>下载 PDF
              </button>
              <button onClick={() => setShowWeeklyModal(false)} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 cursor-pointer whitespace-nowrap">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* 月报弹窗 */}
      {showMonthlyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
              <h2 className="text-base font-semibold text-gray-900">学习月报 · 2026年3月</h2>
              <button onClick={() => setShowMonthlyModal(false)} className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                <i className="ri-close-line text-xl"></i>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: '总学习时长', value: '76.5h', color: 'teal' },
                  { label: '作业完成', value: '15/16', color: 'green' },
                  { label: 'AI提问', value: '189次', color: 'sky' },
                  { label: '闪卡复习', value: '628张', color: 'violet' },
                ].map((s, i) => (
                  <div key={i} className={`p-3 bg-${s.color}-50 rounded-lg border border-${s.color}-100 text-center`}>
                    <div className={`text-xl font-bold text-${s.color}-600`}>{s.value}</div>
                    <div className="text-xs text-gray-500 mt-1">{s.label}</div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">月度平均分</div>
                  <div className="text-2xl font-bold text-gray-900">89.5</div>
                  <div className="text-xs text-green-600 mt-1"><i className="ri-arrow-up-line"></i> 较上月 +5.2</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">班级排名</div>
                  <div className="text-2xl font-bold text-gray-900">8 / 45</div>
                  <div className="text-xs text-green-600 mt-1"><i className="ri-arrow-up-line"></i> 较上月上升 3名</div>
                </div>
              </div>
              <div className="p-4 bg-green-50 rounded-lg border border-green-100 space-y-2">
                <div className="text-xs font-semibold text-green-700">本月亮点</div>
                {['获得"学习达人"徽章 · 连续打卡30天', '第5章作业获满分 · 教师好评', '提问质量高 · 3次被推荐为精华问题'].map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-700">
                    <i className="ri-star-fill text-green-500"></i>{t}
                  </div>
                ))}
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2 flex-shrink-0">
              <button onClick={() => setShowMonthlyModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 cursor-pointer whitespace-nowrap">
                <i className="ri-download-line mr-1"></i>下载 PDF
              </button>
              <button onClick={() => setShowMonthlyModal(false)} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 cursor-pointer whitespace-nowrap">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* 导出弹窗 */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-base font-semibold text-gray-900">导出学习数据</h2>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">导出格式</label>
                <div className="flex gap-3">
                  {[{ v: 'csv', label: 'CSV', sub: '适合 Excel' }, { v: 'excel', label: 'Excel', sub: '含图表格式' }].map(opt => (
                    <label key={opt.v} className={`flex-1 flex items-center gap-3 p-3 border-2 rounded-lg cursor-pointer transition-colors ${exportFormat === opt.v ? 'border-teal-400 bg-teal-50' : 'border-gray-200 hover:border-teal-200'}`}>
                      <input type="radio" name="fmt" value={opt.v} checked={exportFormat === opt.v} onChange={() => setExportFormat(opt.v)} className="w-4 h-4 accent-teal-600" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">{opt.label}</div>
                        <div className="text-xs text-gray-500">{opt.sub}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">导出内容</label>
                <div className="space-y-2">
                  {[
                    { key: 'studyTime', label: '学习时长记录' },
                    { key: 'homework', label: '作业完成情况' },
                    { key: 'aiQuestions', label: 'AI提问历史' },
                    { key: 'attendance', label: '出勤记录' },
                    { key: 'grades', label: '成绩记录' },
                  ].map(f => (
                    <label key={f.key} className="flex items-center gap-3 p-2.5 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100">
                      <input
                        type="checkbox"
                        checked={exportFields[f.key as keyof typeof exportFields]}
                        onChange={e => setExportFields({ ...exportFields, [f.key]: e.target.checked })}
                        className="w-4 h-4 accent-teal-600"
                      />
                      <span className="text-sm text-gray-800">{f.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3 flex-shrink-0">
              <button onClick={() => setShowExportModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap">取消</button>
              <button onClick={handleExportLearningData} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 cursor-pointer whitespace-nowrap">确认导出</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
