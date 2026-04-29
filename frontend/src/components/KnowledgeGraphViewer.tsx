import { useEffect, useMemo, useRef, useState } from "react";
import {
  getKnowledgeGraphNeighborIds,
  getKnowledgeGraphRootIds,
  getVisibleKnowledgeGraph,
  normalizeKnowledgeGraph,
} from "@/lib/knowledge-graph";
import type {
  KnowledgeGraphData,
  KnowledgeGraphEdge,
  KnowledgeGraphNode,
} from "@/types/course";

interface KnowledgeGraphViewerProps {
  title?: string;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  rootIds?: string[];
  className?: string;
  heightClassName?: string;
  showCloseButton?: boolean;
  onClose?: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  course: "课程",
  material: "资料",
  concept: "概念",
  candidate_concept: "候选概念",
  algorithm: "算法",
  formula: "公式",
  table: "表格",
  image: "图片",
  content: "内容",
};

function formatType(type?: string) {
  if (!type) return "未分类";
  return TYPE_LABELS[type] ?? type;
}

function formatPercent(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value)) return "未知";
  return `${Math.round(value * 100)}%`;
}

function getNodeTypeOptions(nodes: KnowledgeGraphNode[]) {
  return Array.from(new Set(nodes.map((node) => node.type || "concept")))
    .filter(Boolean)
    .sort((a, b) => formatType(a).localeCompare(formatType(b), "zh-Hans-CN"));
}

function buildGraphData(
  nodes: KnowledgeGraphNode[],
  edges: KnowledgeGraphEdge[],
  rootIds?: string[],
): KnowledgeGraphData {
  return {
    nodes,
    edges,
    meta: { rootNodeId: rootIds?.[0] ?? null },
  };
}

function computeViewBox(nodes: KnowledgeGraphNode[]) {
  if (nodes.length === 0) return "-120 -120 240 240";

  const xs = nodes.map((node) => Number.isFinite(node.x) ? node.x : 0);
  const ys = nodes.map((node) => Number.isFinite(node.y) ? node.y : 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const padding = 120;
  const width = Math.max(maxX - minX + padding * 2, 420);
  const height = Math.max(maxY - minY + padding * 2, 300);
  return `${minX - padding} ${minY - padding} ${width} ${height}`;
}

function getEdgeLabel(edge: KnowledgeGraphEdge) {
  return edge.label || edge.relationType || "related_to";
}

function serializeSmallJson(value?: Record<string, unknown>) {
  if (!value || Object.keys(value).length === 0) return "暂无";
  return JSON.stringify(value, null, 2);
}

export default function KnowledgeGraphViewer({
  title = "知识图谱可视化",
  nodes,
  edges,
  rootIds,
  className = "",
  heightClassName = "h-[520px]",
  showCloseButton = false,
  onClose,
}: KnowledgeGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const normalized = useMemo(() => normalizeKnowledgeGraph(buildGraphData(nodes, edges, rootIds)), [edges, nodes, rootIds]);
  const resolvedRootIds = useMemo(() => {
    const explicitRoots = rootIds?.filter((id) => normalized.nodes.some((node) => node.id === id));
    return explicitRoots && explicitRoots.length > 0 ? explicitRoots : getKnowledgeGraphRootIds(normalized);
  }, [normalized, rootIds]);
  const [expandedNodeIds, setExpandedNodeIds] = useState<string[]>(resolvedRootIds);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [minConfidence, setMinConfidence] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    setExpandedNodeIds(resolvedRootIds);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, [resolvedRootIds]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const filteredNodeIds = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return new Set(
      normalized.nodes
        .filter((node) => typeFilter === "all" || (node.type || "concept") === typeFilter)
        .filter((node) => {
          if (!normalizedQuery) return true;
          return [node.label, node.description, node.type]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(normalizedQuery));
        })
        .filter((node) => {
          if (!minConfidence) return true;
          if (typeof node.confidence !== "number") return node.type === "course";
          return node.confidence >= minConfidence;
        })
        .map((node) => node.id),
    );
  }, [minConfidence, normalized.nodes, query, typeFilter]);

  const visible = useMemo(() => {
    const graph = getVisibleKnowledgeGraph(
      { ...normalized, meta: { rootNodeId: resolvedRootIds[0] ?? null } },
      expandedNodeIds,
      { undirected: true },
    );
    const visibleNodes = graph.nodes.filter((node) => filteredNodeIds.has(node.id));
    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
    return {
      nodes: visibleNodes,
      edges: graph.edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)),
    };
  }, [expandedNodeIds, filteredNodeIds, normalized, resolvedRootIds]);

  const nodeById = useMemo(() => {
    return new Map(normalized.nodes.map((node) => [node.id, node]));
  }, [normalized.nodes]);
  const visibleNodeById = useMemo(() => {
    return new Map(visible.nodes.map((node) => [node.id, node]));
  }, [visible.nodes]);
  const typeOptions = useMemo(() => getNodeTypeOptions(normalized.nodes), [normalized.nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) ?? null : null;
  const selectedEdge = selectedEdgeId ? normalized.edges.find((edge) => edge.id === selectedEdgeId) ?? null : null;
  const viewBox = useMemo(() => computeViewBox(visible.nodes), [visible.nodes]);
  const matchedNodeIds = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return new Set<string>();
    return new Set(
      normalized.nodes
        .filter((node) =>
          [node.label, node.description, node.type]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
        )
        .map((node) => node.id),
    );
  }, [normalized.nodes, query]);

  const toggleNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
    const neighborIds = getKnowledgeGraphNeighborIds(normalized.edges, nodeId, { undirected: true });
    if (neighborIds.length === 0) return;
    setExpandedNodeIds((previous) =>
      previous.includes(nodeId)
        ? previous.filter((id) => id !== nodeId)
        : [...previous, nodeId],
    );
  };

  const expandAll = () => setExpandedNodeIds(normalized.nodes.map((node) => node.id));
  const reset = () => {
    setExpandedNodeIds(resolvedRootIds);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setQuery("");
    setTypeFilter("all");
    setMinConfidence(0);
  };

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      await containerRef.current.requestFullscreen();
      return;
    }
    await document.exitFullscreen();
  };

  return (
    <div ref={containerRef} className={`bg-white rounded-lg border border-gray-200 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <div className="mt-1 text-xs text-gray-500">
            {normalized.nodes.length} 个节点 / {normalized.edges.length} 条关系，当前显示 {visible.nodes.length} 个节点
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={reset} className="rounded-md bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100">
            <i className="ri-refresh-line mr-1"></i>重置
          </button>
          <button onClick={expandAll} className="rounded-md bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100">
            <i className="ri-node-tree mr-1"></i>展开全部
          </button>
          <button onClick={() => void toggleFullscreen()} className="rounded-md bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100">
            <i className={`${isFullscreen ? "ri-fullscreen-exit-line" : "ri-fullscreen-line"} mr-1`}></i>
            {isFullscreen ? "退出全屏" : "全屏"}
          </button>
          {showCloseButton && (
            <button onClick={onClose} className="flex h-8 w-8 items-center justify-center text-gray-400 hover:text-gray-600">
              <i className="ri-close-line text-xl"></i>
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 px-5 py-3">
            <div className="relative min-w-[220px] flex-1">
              <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-400"></i>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索节点或描述"
                className="h-9 w-full rounded-md border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-teal-500"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className="h-9 rounded-md border border-gray-200 px-3 text-sm text-gray-700 outline-none focus:border-teal-500"
            >
              <option value="all">全部类型</option>
              {typeOptions.map((type) => (
                <option key={type} value={type}>{formatType(type)}</option>
              ))}
            </select>
            <label className="flex h-9 items-center gap-2 rounded-md border border-gray-200 px-3 text-xs text-gray-600">
              置信度
              <input
                type="range"
                min="0"
                max="0.95"
                step="0.05"
                value={minConfidence}
                onChange={(event) => setMinConfidence(Number(event.target.value))}
              />
              <span className="w-9 text-right">{formatPercent(minConfidence)}</span>
            </label>
          </div>

          <div className={`${isFullscreen ? "h-[calc(100vh-138px)]" : heightClassName} relative overflow-hidden bg-gray-50`}>
            {visible.nodes.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center text-gray-500">
                <i className="ri-mind-map text-4xl text-gray-300"></i>
                <div className="mt-3 text-sm font-medium text-gray-700">暂无可显示的图谱节点</div>
                <div className="mt-1 text-xs text-gray-400">可以重置过滤条件，或等待资料索引完成后刷新。</div>
              </div>
            ) : (
              <svg className="h-full w-full" viewBox={viewBox} role="img" aria-label={title}>
                {visible.edges.map((edge) => {
                  const sourceNode = visibleNodeById.get(edge.source);
                  const targetNode = visibleNodeById.get(edge.target);
                  if (!sourceNode || !targetNode) return null;
                  const midX = (sourceNode.x + targetNode.x) / 2;
                  const midY = (sourceNode.y + targetNode.y) / 2;
                  const isSelected = selectedEdgeId === edge.id;
                  return (
                    <g key={edge.id} className="cursor-pointer" onClick={() => { setSelectedEdgeId(edge.id); setSelectedNodeId(null); }}>
                      <line
                        x1={sourceNode.x}
                        y1={sourceNode.y}
                        x2={targetNode.x}
                        y2={targetNode.y}
                        stroke={isSelected ? "#0f766e" : edge.color || "#cbd5e1"}
                        strokeWidth={isSelected ? 3 : 1.8}
                        strokeDasharray={edge.dashed ? "5 4" : undefined}
                      />
                      <text x={midX} y={midY - 6} textAnchor="middle" className="fill-gray-500 text-[10px] font-medium">
                        {getEdgeLabel(edge)}
                      </text>
                    </g>
                  );
                })}

                {visible.nodes.map((node) => {
                  const neighborCount = getKnowledgeGraphNeighborIds(normalized.edges, node.id, { undirected: true }).length;
                  const isExpanded = expandedNodeIds.includes(node.id);
                  const isSelected = selectedNodeId === node.id;
                  const isMatched = matchedNodeIds.has(node.id);
                  const radius = node.type === "course" ? 34 : node.type === "material" ? 29 : 24;
                  return (
                    <g key={node.id} className="cursor-pointer" onClick={() => toggleNode(node.id)}>
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={radius + (isSelected || isMatched ? 6 : 0)}
                        fill={isMatched ? "#fef3c7" : "transparent"}
                        stroke={isSelected ? "#0f766e" : isMatched ? "#f59e0b" : "transparent"}
                        strokeWidth="3"
                      />
                      <circle cx={node.x} cy={node.y} r={radius} fill={node.color || "#475569"} className="transition-opacity hover:opacity-80" />
                      {neighborCount > 0 && (
                        <>
                          <circle cx={node.x + radius - 4} cy={node.y - radius + 4} r="10" fill="white" stroke="#cbd5e1" />
                          <text x={node.x + radius - 4} y={node.y - radius + 8} textAnchor="middle" className="select-none fill-gray-700 text-[11px] font-bold">
                            {isExpanded ? "-" : "+"}
                          </text>
                        </>
                      )}
                      <text x={node.x} y={node.y + radius + 20} textAnchor="middle" className="select-none fill-gray-700 text-[12px] font-medium">
                        {node.label.length > 18 ? `${node.label.slice(0, 18)}...` : node.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}

            <div className="absolute bottom-4 left-4 max-w-[calc(100%-2rem)] rounded-lg border border-gray-200 bg-white/95 p-3 shadow-sm">
              <div className="mb-2 text-xs font-semibold text-gray-900">类型图例</div>
              <div className="flex flex-wrap gap-2">
                {typeOptions.slice(0, 8).map((type) => {
                  const sample = normalized.nodes.find((node) => (node.type || "concept") === type);
                  return (
                    <div key={type} className="flex items-center gap-1.5 text-xs text-gray-600">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: sample?.color || "#475569" }}></span>
                      <span>{formatType(type)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <aside className="border-t border-gray-100 bg-white p-5 lg:border-l lg:border-t-0">
          {selectedNode ? (
            <div>
              <div className="text-xs font-semibold uppercase text-teal-600">节点详情</div>
              <h3 className="mt-2 text-base font-semibold text-gray-900">{selectedNode.label}</h3>
              <div className="mt-3 space-y-2 text-sm text-gray-600">
                <div>类型：{formatType(selectedNode.type)}</div>
                <div>置信度：{formatPercent(selectedNode.confidence)}</div>
                <div>邻居节点：{getKnowledgeGraphNeighborIds(normalized.edges, selectedNode.id, { undirected: true }).length}</div>
              </div>
              {selectedNode.description && (
                <p className="mt-4 rounded-md bg-gray-50 p-3 text-sm leading-6 text-gray-700">{selectedNode.description}</p>
              )}
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">来源信息</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedNode.sourceSpan)}
                </pre>
              </details>
            </div>
          ) : selectedEdge ? (
            <div>
              <div className="text-xs font-semibold uppercase text-teal-600">关系详情</div>
              <h3 className="mt-2 text-base font-semibold text-gray-900">{getEdgeLabel(selectedEdge)}</h3>
              <div className="mt-3 space-y-2 text-sm text-gray-600">
                <div>起点：{nodeById.get(selectedEdge.source)?.label || selectedEdge.source}</div>
                <div>终点：{nodeById.get(selectedEdge.target)?.label || selectedEdge.target}</div>
                <div>置信度：{formatPercent(selectedEdge.confidence)}</div>
              </div>
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">关系来源</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedEdge.sourceSpan)}
                </pre>
              </details>
            </div>
          ) : (
            <div className="flex h-full min-h-[220px] flex-col justify-center text-sm text-gray-500">
              <i className="ri-cursor-line mb-3 text-3xl text-gray-300"></i>
              <div className="font-medium text-gray-700">选择一个节点或关系</div>
              <div className="mt-2 leading-6">点击节点可查看描述、置信度与来源；带加号的节点可继续展开邻居。</div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
