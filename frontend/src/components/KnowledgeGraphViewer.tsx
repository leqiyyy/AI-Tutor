import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, MouseEvent, WheelEvent } from "react";
import {
  getKnowledgeGraphNeighborIds,
  getKnowledgeGraphRootIds,
  getVisibleKnowledgeGraph,
  normalizeKnowledgeGraph,
} from "@/lib/knowledge-graph";
import type {
  CourseRole,
  KnowledgeGraphData,
  KnowledgeGraphEdge,
  KnowledgeGraphEvidenceData,
  KnowledgeGraphNode,
} from "@/types/course";
import { courseService, fetchAuthenticatedObjectUrl } from "@/services/course";

interface KnowledgeGraphViewerProps {
  title?: string;
  courseId?: string;
  role?: CourseRole;
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
  const normalized = String(type || "").trim().toLowerCase();
  if (!normalized || ["unknown", "none", "null", "undefined"].includes(normalized)) return "未分类";
  return TYPE_LABELS[normalized] ?? normalized;
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

function parseViewBox(value: string) {
  const [x, y, width, height] = value.split(/\s+/).map((item) => Number(item));
  return {
    x: Number.isFinite(x) ? x : -120,
    y: Number.isFinite(y) ? y : -120,
    width: Number.isFinite(width) && width > 0 ? width : 240,
    height: Number.isFinite(height) && height > 0 ? height : 240,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function stableHash(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function layoutVisibleGraph(
  nodes: KnowledgeGraphNode[],
  edges: KnowledgeGraphEdge[],
  rootIds: string[],
): KnowledgeGraphNode[] {
  if (nodes.length <= 1) return nodes;

  const rootSet = new Set(rootIds);
  const degreeById = new Map<string, number>();
  edges.forEach((edge) => {
    degreeById.set(edge.source, (degreeById.get(edge.source) || 0) + 1);
    degreeById.set(edge.target, (degreeById.get(edge.target) || 0) + 1);
  });

  const roots = nodes.filter((node) => rootSet.has(node.id));
  const nonRoots = nodes
    .filter((node) => !rootSet.has(node.id))
    .sort((a, b) => {
      const degreeDiff = (degreeById.get(b.id) || 0) - (degreeById.get(a.id) || 0);
      if (degreeDiff !== 0) return degreeDiff;
      const angleA = Math.atan2(Number.isFinite(a.y) ? a.y : 0, Number.isFinite(a.x) ? a.x : 0);
      const angleB = Math.atan2(Number.isFinite(b.y) ? b.y : 0, Number.isFinite(b.x) ? b.x : 0);
      if (angleA !== angleB) return angleA - angleB;
      return stableHash(a.id) - stableHash(b.id);
    });

  const positioned = new Map<string, KnowledgeGraphNode>();
  roots.forEach((node, index) => {
    const offset = roots.length === 1 ? 0 : (index - (roots.length - 1) / 2) * 96;
    positioned.set(node.id, { ...node, x: offset, y: 0 });
  });

  const minGap = 92;
  const ringGap = 106;
  let ring = 0;
  let cursor = 0;
  while (cursor < nonRoots.length) {
    const radius = 170 + ring * ringGap;
    const capacity = Math.max(8, Math.floor((2 * Math.PI * radius) / minGap));
    const ringNodes = nonRoots.slice(cursor, cursor + capacity);
    const angleOffset = ring % 2 === 0 ? -Math.PI / 2 : -Math.PI / 2 + Math.PI / Math.max(ringNodes.length, 1);
    ringNodes.forEach((node, index) => {
      const angle = angleOffset + (2 * Math.PI * index) / ringNodes.length;
      positioned.set(node.id, {
        ...node,
        x: Math.round(Math.cos(angle) * radius * 100) / 100,
        y: Math.round(Math.sin(angle) * radius * 100) / 100,
      });
    });
    cursor += capacity;
    ring += 1;
  }

  return nodes.map((node) => positioned.get(node.id) || node);
}

function getEdgeLabel(edge: KnowledgeGraphEdge) {
  return edge.label || edge.relationType || "related_to";
}

function serializeSmallJson(value?: Record<string, unknown>) {
  if (!value || Object.keys(value).length === 0) return "暂无";
  return JSON.stringify(value, null, 2);
}

function getMasteryMeta(node?: KnowledgeGraphNode | null) {
  const status = node?.learningStatus || "unknown";
  const mastery = typeof node?.masteryScore === "number" ? node.masteryScore : null;
  const fallbackLabel = mastery == null ? "暂无学习证据" : `${Math.round(mastery * 100)}%`;
  const map: Record<string, { label: string; className: string; ring: string; fill: string }> = {
    mastered: {
      label: `已掌握 ${fallbackLabel}`,
      className: "bg-emerald-50 text-emerald-700 border-emerald-100",
      ring: "#10b981",
      fill: "#ecfdf5",
    },
    learning: {
      label: `学习中 ${fallbackLabel}`,
      className: "bg-sky-50 text-sky-700 border-sky-100",
      ring: "#0ea5e9",
      fill: "#eff6ff",
    },
    needs_review: {
      label: `待巩固 ${fallbackLabel}`,
      className: "bg-amber-50 text-amber-700 border-amber-100",
      ring: "#f59e0b",
      fill: "#fffbeb",
    },
    weak: {
      label: `薄弱 ${fallbackLabel}`,
      className: "bg-rose-50 text-rose-700 border-rose-100",
      ring: "#f43f5e",
      fill: "#fff1f2",
    },
    unknown: {
      label: "暂无学习证据",
      className: "bg-gray-50 text-gray-600 border-gray-100",
      ring: "#cbd5e1",
      fill: "#f8fafc",
    },
  };
  return map[status] || map.unknown;
}

function relationLabelText(label?: string) {
  const normalized = String(label || "related_to").toLowerCase();
  const map: Record<string, string> = {
    prerequisite: "先修",
    requires: "依赖",
    before: "前置",
    part_of: "组成",
    contains: "包含",
    related_to: "相关",
    causes: "导致",
    contrasts_with: "对比",
    example_of: "例子",
    concept: "课程概念",
  };
  return map[normalized] || label || "相关";
}

function provenanceSummary(value?: Record<string, unknown>) {
  if (!value || Object.keys(value).length === 0) return "暂无明确溯源";
  const materials = Array.isArray(value.sourceMaterials) ? value.sourceMaterials : [];
  if (materials.length > 0) {
    return materials
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const material = item as Record<string, unknown>;
        return material.title || material.fileName || material.id || "";
      })
      .filter(Boolean)
      .slice(0, 3)
      .join("、");
  }
  const candidates = [
    value.sourceName,
    value.materialTitle,
    value.fileName,
    value.source_name,
    value.file_name,
    value.material_title,
    value.doc_id,
    value.material_id,
    value.source_material_id,
  ].filter(Boolean);
  return candidates.length > 0 ? String(candidates[0]) : "已记录结构化溯源";
}

function formatBBox(value: unknown) {
  if (!Array.isArray(value) || value.length < 4) return "";
  const parts = value.slice(0, 4).map((item) => Number(item));
  if (parts.some((item) => Number.isNaN(item))) return "";
  return parts.map((item) => Math.round(item * 100) / 100).join(", ");
}

function normalizedBBoxStyle(value: unknown): CSSProperties | null {
  if (!Array.isArray(value) || value.length < 4) return null;
  const parts = value.slice(0, 4).map((item) => Number(item));
  if (parts.some((item) => Number.isNaN(item))) return null;
  const max = Math.max(...parts);
  const min = Math.min(...parts);
  if (min < 0 || max > 1) return null;
  const [x1, y1, x2, y2] = parts;
  const width = Math.max(0.01, x2 - x1);
  const height = Math.max(0.01, y2 - y1);
  return {
    left: `${x1 * 100}%`,
    top: `${y1 * 100}%`,
    width: `${width * 100}%`,
    height: `${height * 100}%`,
  };
}

function compactText(value: unknown, maxLength = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function evidenceItemsFrom(sourceSpan?: Record<string, unknown>) {
  const raw = sourceSpan?.evidence_items;
  return Array.isArray(raw)
    ? raw.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object").slice(0, 5)
    : [];
}

function relationEvidenceText(edge: KnowledgeGraphEdge) {
  const candidates = [
    edge.sourceSpan?.evidence,
    (edge.provenance?.raganything_relation as Record<string, unknown> | undefined)?.description,
    (edge.provenance?.raganything_relation as Record<string, unknown> | undefined)?.summary,
    (edge.provenance?.raganything_relation as Record<string, unknown> | undefined)?.evidence,
    edge.description,
    edge.summary,
  ];
  for (const candidate of candidates) {
    const text = compactText(candidate, 360);
    if (text) return text;
  }
  return "";
}

export default function KnowledgeGraphViewer({
  title = "知识图谱可视化",
  courseId,
  role,
  nodes,
  edges,
  rootIds,
  className = "",
  heightClassName = "h-[520px]",
  showCloseButton = false,
  onClose,
}: KnowledgeGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphPaneRef = useRef<HTMLDivElement>(null);
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
  const [evidencePanel, setEvidencePanel] = useState<KnowledgeGraphEvidenceData | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [evidenceLoadingKey, setEvidenceLoadingKey] = useState<string | null>(null);
  const [evidenceObject, setEvidenceObject] = useState<{ url: string; contentType: string; source: "asset" | "material" } | null>(null);
  const [evidenceObjectLoading, setEvidenceObjectLoading] = useState(false);
  const [evidenceObjectError, setEvidenceObjectError] = useState<string | null>(null);
  const [viewport, setViewport] = useState({ zoom: 1, offsetX: 0, offsetY: 0 });
  const [dragStart, setDragStart] = useState<{
    clientX: number;
    clientY: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  useEffect(() => {
    setExpandedNodeIds(resolvedRootIds);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setEvidencePanel(null);
    setEvidenceError(null);
    setEvidenceObject(null);
    setEvidenceObjectError(null);
  }, [resolvedRootIds]);

  useEffect(() => {
    if (!evidencePanel) {
      setEvidenceObject(null);
      setEvidenceObjectError(null);
      setEvidenceObjectLoading(false);
      return undefined;
    }
    const sourceUrl = evidencePanel.asset?.imageUrl || evidencePanel.material?.viewUrl;
    const sourceKind = evidencePanel.asset?.imageUrl ? "asset" : "material";
    if (!sourceUrl) {
      setEvidenceObject(null);
      setEvidenceObjectError(null);
      setEvidenceObjectLoading(false);
      return undefined;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setEvidenceObject(null);
    setEvidenceObjectError(null);
    setEvidenceObjectLoading(true);
    fetchAuthenticatedObjectUrl(sourceUrl)
      .then((result) => {
        objectUrl = result.objectUrl;
        if (!cancelled) {
          setEvidenceObject({ url: result.objectUrl, contentType: result.contentType, source: sourceKind });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setEvidenceObjectError(error instanceof Error ? error.message : "证据原文加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setEvidenceObjectLoading(false);
        }
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [evidencePanel]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  const normalizedQuery = query.trim().toLowerCase();

  const filteredNodeIds = useMemo(() => {
    const rootSet = new Set(resolvedRootIds);
    return new Set(
      normalized.nodes
        .filter((node) => rootSet.has(node.id) || typeFilter === "all" || (node.type || "concept") === typeFilter)
        .filter((node) => {
          if (rootSet.has(node.id)) return true;
          if (!minConfidence) return true;
          if (typeof node.confidence !== "number") return node.type === "course";
          return node.confidence >= minConfidence;
        })
        .map((node) => node.id),
    );
  }, [minConfidence, normalized.nodes, resolvedRootIds, typeFilter]);

  const matchedNodeIds = useMemo(() => {
    if (!normalizedQuery) return new Set<string>();
    return new Set(
      normalized.nodes
        .filter((node) => filteredNodeIds.has(node.id))
        .filter((node) =>
          [node.label, node.description, node.type]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
        )
        .map((node) => node.id),
    );
  }, [filteredNodeIds, normalized.nodes, normalizedQuery]);

  const visible = useMemo(() => {
    const graph = getVisibleKnowledgeGraph(
      { ...normalized, meta: { rootNodeId: resolvedRootIds[0] ?? null } },
      expandedNodeIds,
      { undirected: true },
    );
    const visibleNodeIds = new Set(
      graph.nodes
        .filter((node) => filteredNodeIds.has(node.id))
        .map((node) => node.id),
    );
    if (normalizedQuery) {
      matchedNodeIds.forEach((nodeId) => visibleNodeIds.add(nodeId));
      resolvedRootIds.forEach((nodeId) => visibleNodeIds.add(nodeId));
    }
    const visibleNodes = normalized.nodes.filter((node) => visibleNodeIds.has(node.id));
    const candidateEdges = normalizedQuery ? normalized.edges : graph.edges;
    const visibleEdges = candidateEdges.filter((edge) => {
      if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) return false;
      if (!minConfidence || typeof edge.confidence !== "number") return true;
      return edge.confidence >= minConfidence;
    });
    return {
      nodes: visibleNodes,
      edges: visibleEdges,
    };
  }, [expandedNodeIds, filteredNodeIds, matchedNodeIds, minConfidence, normalized, normalizedQuery, resolvedRootIds]);

  const fullLayoutNodeById = useMemo(() => {
    const layoutNodeIds = new Set(filteredNodeIds);
    const layoutNodes = normalized.nodes.filter((node) => layoutNodeIds.has(node.id));
    const layoutEdges = normalized.edges.filter((edge) => {
      if (!layoutNodeIds.has(edge.source) || !layoutNodeIds.has(edge.target)) return false;
      if (!minConfidence || typeof edge.confidence !== "number") return true;
      return edge.confidence >= minConfidence;
    });
    return new Map(
      layoutVisibleGraph(layoutNodes, layoutEdges, resolvedRootIds)
        .map((node) => [node.id, node]),
    );
  }, [filteredNodeIds, minConfidence, normalized.edges, normalized.nodes, resolvedRootIds]);

  const displayVisible = useMemo(() => ({
    nodes: visible.nodes.map((node) => fullLayoutNodeById.get(node.id) || node),
    edges: visible.edges,
  }), [fullLayoutNodeById, visible.edges, visible.nodes]);

  const nodeById = useMemo(() => {
    return new Map(normalized.nodes.map((node) => [node.id, node]));
  }, [normalized.nodes]);
  const visibleNodeById = useMemo(() => {
    return new Map(displayVisible.nodes.map((node) => [node.id, node]));
  }, [displayVisible.nodes]);
  const typeOptions = useMemo(() => getNodeTypeOptions(normalized.nodes), [normalized.nodes]);
  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) ?? null : null;
  const selectedEdge = selectedEdgeId ? normalized.edges.find((edge) => edge.id === selectedEdgeId) ?? null : null;
  const selectedNodeEvidenceItems = evidenceItemsFrom(selectedNode?.sourceSpan);
  const selectedEdgeEvidenceItems = evidenceItemsFrom(selectedEdge?.sourceSpan);
  const selectedEdgeEvidenceText = selectedEdge ? relationEvidenceText(selectedEdge) : "";
  const openEvidencePanel = async (recordType: "node" | "edge", recordId: string, evidenceIndex: number) => {
    const key = `${recordType}:${recordId}:${evidenceIndex}`;
    setEvidenceError(null);
    if (!courseId || !role) {
      setEvidenceError("当前页面未传入课程上下文，暂只能查看卡片中的定位线索。");
      return;
    }
    setEvidenceLoadingKey(key);
    try {
      const payload = await courseService.getKnowledgeGraphEvidence(courseId, role, {
        recordType,
        recordId,
        evidenceIndex,
      });
      setEvidencePanel(payload);
    } catch (error) {
      setEvidenceError(error instanceof Error ? error.message : "证据解析失败");
    } finally {
      setEvidenceLoadingKey(null);
    }
  };
  const selectedNodeNeighbors = selectedNode
    ? getKnowledgeGraphNeighborIds(normalized.edges, selectedNode.id, { undirected: true })
      .map((nodeId) => nodeById.get(nodeId))
      .filter((node): node is KnowledgeGraphNode => Boolean(node))
      .slice(0, 8)
    : [];
  const selectedOneHop = useMemo(() => {
    if (!selectedNodeId) return { nodeIds: new Set<string>(), edgeIds: new Set<string>() };
    const rootSet = new Set(resolvedRootIds);
    const selectedIsRoot = rootSet.has(selectedNodeId);
    const nodeIds = new Set<string>([selectedNodeId]);
    const edgeIds = new Set<string>();
    displayVisible.edges.forEach((edge) => {
      if (edge.source === selectedNodeId || edge.target === selectedNodeId) {
        const isCourseEntryEdge = rootSet.has(edge.source) || rootSet.has(edge.target);
        if (isCourseEntryEdge && !selectedIsRoot) return;
        edgeIds.add(edge.id);
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
      }
    });
    return { nodeIds, edgeIds };
  }, [displayVisible.edges, resolvedRootIds, selectedNodeId]);
  const baseViewBox = useMemo(() => parseViewBox(computeViewBox(displayVisible.nodes)), [displayVisible.nodes]);
  const viewBox = useMemo(() => {
    const width = baseViewBox.width / viewport.zoom;
    const height = baseViewBox.height / viewport.zoom;
    const x = baseViewBox.x + (baseViewBox.width - width) / 2 + viewport.offsetX;
    const y = baseViewBox.y + (baseViewBox.height - height) / 2 + viewport.offsetY;
    return `${x} ${y} ${width} ${height}`;
  }, [baseViewBox, viewport]);

  const zoomBy = (factor: number) => {
    setViewport((current) => ({
      ...current,
      zoom: clamp(current.zoom * factor, 0.55, 3.5),
    }));
  };

  const resetViewport = () => {
    setViewport({ zoom: 1, offsetX: 0, offsetY: 0 });
    setDragStart(null);
  };

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    zoomBy(event.deltaY > 0 ? 0.9 : 1.1);
  };

  const handleMouseMove = (event: MouseEvent<HTMLDivElement>) => {
    if (!dragStart || !graphPaneRef.current) return;
    const rect = graphPaneRef.current.getBoundingClientRect();
    const unitX = (baseViewBox.width / viewport.zoom) / Math.max(rect.width, 1);
    const unitY = (baseViewBox.height / viewport.zoom) / Math.max(rect.height, 1);
    setViewport((current) => ({
      ...current,
      offsetX: dragStart.offsetX - (event.clientX - dragStart.clientX) * unitX,
      offsetY: dragStart.offsetY - (event.clientY - dragStart.clientY) * unitY,
    }));
  };

  const toggleNode = (nodeId: string) => {
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      return;
    }
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
    resetViewport();
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
              证据强度
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

          <div
            ref={graphPaneRef}
            className={`${isFullscreen ? "h-[calc(100vh-138px)]" : heightClassName} relative overflow-hidden bg-gray-50 ${dragStart ? "cursor-grabbing" : "cursor-grab"}`}
            onWheel={handleWheel}
            onMouseMove={handleMouseMove}
            onMouseUp={() => setDragStart(null)}
            onMouseLeave={() => setDragStart(null)}
            onMouseDown={(event) => {
              if (event.button !== 0) return;
              setDragStart({
                clientX: event.clientX,
                clientY: event.clientY,
                offsetX: viewport.offsetX,
                offsetY: viewport.offsetY,
              });
            }}
          >
            {displayVisible.nodes.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center text-gray-500">
                <i className="ri-mind-map text-4xl text-gray-300"></i>
                <div className="mt-3 text-sm font-medium text-gray-700">暂无可显示的图谱节点</div>
                <div className="mt-1 text-xs text-gray-400">可以重置过滤条件，或等待资料索引完成后刷新。</div>
              </div>
            ) : (
              <svg className="h-full w-full" viewBox={viewBox} role="img" aria-label={title}>
                {displayVisible.edges.map((edge) => {
                  const sourceNode = visibleNodeById.get(edge.source);
                  const targetNode = visibleNodeById.get(edge.target);
                  if (!sourceNode || !targetNode) return null;
                  const midX = (sourceNode.x + targetNode.x) / 2;
                  const midY = (sourceNode.y + targetNode.y) / 2;
                  const isSelected = selectedEdgeId === edge.id;
                  const isOneHop = selectedOneHop.edgeIds.has(edge.id);
                  const isDimmed = Boolean(selectedNodeId) && !isOneHop;
                  return (
                    <g
                      key={edge.id}
                      className="cursor-pointer"
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={() => { setSelectedEdgeId(edge.id); setSelectedNodeId(null); }}
                    >
                      <line
                        x1={sourceNode.x}
                        y1={sourceNode.y}
                        x2={targetNode.x}
                        y2={targetNode.y}
                        stroke={isSelected || isOneHop ? "#0f766e" : edge.color || "#cbd5e1"}
                        strokeWidth={isSelected || isOneHop ? 3 : 1.4}
                        opacity={isDimmed ? 0.18 : 1}
                        strokeDasharray={edge.dashed ? "5 4" : undefined}
                      />
                      <text
                        x={midX}
                        y={midY - 6}
                        textAnchor="middle"
                        className={`${isOneHop ? "fill-teal-700" : "fill-gray-500"} text-[10px] font-medium`}
                        opacity={isDimmed ? 0.22 : 1}
                      >
                        {relationLabelText(getEdgeLabel(edge))}
                      </text>
                    </g>
                  );
                })}

                {displayVisible.nodes.map((node) => {
                  const neighborCount = getKnowledgeGraphNeighborIds(normalized.edges, node.id, { undirected: true }).length;
                  const isExpanded = expandedNodeIds.includes(node.id);
                  const isSelected = selectedNodeId === node.id;
                  const isMatched = matchedNodeIds.has(node.id);
                  const isOneHop = selectedOneHop.nodeIds.has(node.id);
                  const isDimmed = Boolean(selectedNodeId) && !isOneHop;
                  const masteryMeta = getMasteryMeta(node);
                  const radius = node.type === "course" ? 28 : node.type === "material" ? 23 : 19;
                  return (
                    <g
                      key={node.id}
                      className="cursor-pointer"
                      opacity={isDimmed ? 0.26 : 1}
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={() => toggleNode(node.id)}
                    >
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={radius + (isSelected || isMatched || isOneHop ? 6 : 0)}
                        fill={isMatched ? "#fef3c7" : node.type === "course" ? "transparent" : masteryMeta.fill}
                        stroke={isSelected ? "#0f766e" : isOneHop ? "#14b8a6" : isMatched ? "#f59e0b" : node.type === "course" ? "transparent" : masteryMeta.ring}
                        strokeWidth={isSelected || isOneHop ? "4" : "3"}
                      />
                      <circle cx={node.x} cy={node.y} r={radius} fill={node.color || "#475569"} className="transition-opacity hover:opacity-80" />
                      {node.type !== "course" && typeof node.masteryScore === "number" && (
                        <text x={node.x} y={node.y + 4} textAnchor="middle" className="select-none fill-white text-[10px] font-bold">
                          {Math.round(node.masteryScore * 100)}
                        </text>
                      )}
                      {neighborCount > 0 && (
                        <>
                          <circle cx={node.x + radius - 4} cy={node.y - radius + 4} r="10" fill="white" stroke="#cbd5e1" />
                          <text x={node.x + radius - 4} y={node.y - radius + 8} textAnchor="middle" className="select-none fill-gray-700 text-[11px] font-bold">
                            {isExpanded ? "-" : "+"}
                          </text>
                        </>
                      )}
                      <text x={node.x} y={node.y + radius + 17} textAnchor="middle" className="select-none fill-gray-700 text-[11px] font-medium">
                        {node.label.length > 14 ? `${node.label.slice(0, 14)}...` : node.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}

            <div
              className="absolute right-4 top-4 flex items-center gap-1 rounded-lg border border-gray-200 bg-white/95 p-1 shadow-sm"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => zoomBy(1.18)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
                title="放大"
              >
                <i className="ri-add-line"></i>
              </button>
              <button
                type="button"
                onClick={() => zoomBy(0.85)}
                className="flex h-8 w-8 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100"
                title="缩小"
              >
                <i className="ri-subtract-line"></i>
              </button>
              <button
                type="button"
                onClick={resetViewport}
                className="rounded-md px-2 text-xs font-medium text-gray-600 hover:bg-gray-100"
                title="重置视图"
              >
                {Math.round(viewport.zoom * 100)}%
              </button>
            </div>

            <div className="absolute bottom-4 left-4 max-w-[calc(100%-2rem)] rounded-lg border border-gray-200 bg-white/95 p-3 shadow-sm">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
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
                <div>
                  <div className="mb-2 text-xs font-semibold text-gray-900">掌握状态</div>
                  <div className="flex flex-wrap gap-2">
                    {[
                      ["mastered", "已掌握"],
                      ["learning", "学习中"],
                      ["needs_review", "待巩固"],
                      ["weak", "薄弱"],
                      ["unknown", "暂无证据"],
                    ].map(([status, label]) => {
                      const meta = getMasteryMeta({ id: status, label, x: 0, y: 0, color: "", learningStatus: status });
                      return (
                        <div key={status} className="flex items-center gap-1.5 text-xs text-gray-600">
                          <span className="h-3 w-3 rounded-full border-2" style={{ borderColor: meta.ring, backgroundColor: meta.fill }}></span>
                          <span>{label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <aside className="border-t border-gray-100 bg-white p-5 lg:border-l lg:border-t-0">
          {selectedNode ? (
            <div>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase text-teal-600">节点详情</div>
                  <h3 className="mt-2 text-base font-semibold text-gray-900">{selectedNode.label}</h3>
                </div>
                <span className={`rounded-full border px-2 py-1 text-xs font-medium ${getMasteryMeta(selectedNode).className}`}>
                  {getMasteryMeta(selectedNode).label}
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">类型</div>
                  <div className="mt-1 font-medium text-gray-800">{formatType(selectedNode.type)}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">证据强度</div>
                  <div className="mt-1 font-medium text-gray-800">{formatPercent(selectedNode.confidence)}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">邻接节点</div>
                  <div className="mt-1 font-medium text-gray-800">{selectedNodeNeighbors.length}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">学习证据</div>
                  <div className="mt-1 font-medium text-gray-800">{selectedNode.masteryEvidenceCount || 0} 条</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="mb-2 text-sm font-semibold text-gray-900">概念说明</div>
                <p className="rounded-md bg-gray-50 p-3 text-sm leading-6 text-gray-700">
                  {selectedNode.description || "暂无稳定描述。建议教师补充定义、课程作用和常见误区。"}
                </p>
              </div>

              {selectedNodeNeighbors.length > 0 && (
                <div className="mt-4">
                  <div className="mb-2 text-sm font-semibold text-gray-900">相关节点</div>
                  <div className="flex flex-wrap gap-2">
                    {selectedNodeNeighbors.map((node) => (
                      <button
                        key={node.id}
                        onClick={() => {
                          setSelectedNodeId(node.id);
                          setSelectedEdgeId(null);
                        }}
                        className="rounded-full border border-gray-200 px-2.5 py-1 text-xs text-gray-600 hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
                      >
                        {node.label.length > 14 ? `${node.label.slice(0, 14)}...` : node.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4 rounded-md border border-gray-100 p-3">
                <div className="text-sm font-semibold text-gray-900">来源概览</div>
                <div className="mt-1 text-xs leading-5 text-gray-500">
                  {provenanceSummary({ ...(selectedNode.provenance || {}), ...(selectedNode.sourceSpan || {}), ...(selectedNode.sourceSummary || {}) })}
                </div>
              </div>

              {selectedNodeEvidenceItems.length > 0 && (
                <div className="mt-4 rounded-md border border-teal-100 bg-teal-50/40 p-3">
                  <div className="text-sm font-semibold text-gray-900">原文定位线索</div>
                  <div className="mt-2 space-y-2">
                    {selectedNodeEvidenceItems.map((item, index) => {
                      const bbox = formatBBox(item.bbox);
                      const preview = compactText(item.formula_latex || item.table_markdown || item.ocr_text, 110);
                      const loading = evidenceLoadingKey === `node:${selectedNode.id}:${index}`;
                      return (
                        <button
                          key={`${String(item.item_id || item.atomic_id || index)}-${index}`}
                          type="button"
                          onClick={() => void openEvidencePanel("node", selectedNode.id, index)}
                          className="w-full rounded-md bg-white p-2 text-left text-xs leading-5 text-gray-600 ring-1 ring-transparent hover:ring-teal-200"
                        >
                          <div className="font-medium text-gray-800">
                            {formatType(String(item.modality || "content"))}
                            {item.page !== undefined ? ` · 第 ${String(item.page)} 页` : ""}
                            {bbox ? ` · bbox: ${bbox}` : ""}
                            {loading ? " · 解析中..." : ""}
                          </div>
                          {preview && <div className="mt-1 text-gray-500">{preview}</div>}
                          {(item.image_path || item.source_path) && (
                            <div className="mt-1 truncate text-teal-700">{String(item.image_path || item.source_path)}</div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">结构化来源</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedNode.sourceSpan)}
                </pre>
              </details>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">Provenance</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedNode.provenance)}
                </pre>
              </details>
            </div>
          ) : selectedEdge ? (
            <div>
              <div className="text-xs font-semibold uppercase text-teal-600">关系详情</div>
              <h3 className="mt-2 text-base font-semibold text-gray-900">{relationLabelText(getEdgeLabel(selectedEdge))}</h3>
              <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 p-3">
                <div className="text-xs text-gray-400">关系路径</div>
                <div className="mt-2 text-sm font-medium leading-6 text-gray-800">
                  {nodeById.get(selectedEdge.source)?.label || selectedEdge.source}
                  <i className="ri-arrow-right-line mx-2 text-gray-400"></i>
                  {nodeById.get(selectedEdge.target)?.label || selectedEdge.target}
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">证据强度</div>
                  <div className="mt-1 font-medium text-gray-800">{formatPercent(selectedEdge.confidence)}</div>
                </div>
                <div className="rounded-md bg-gray-50 p-2">
                  <div className="text-gray-400">关系权重</div>
                  <div className="mt-1 font-medium text-gray-800">{selectedEdge.weight ?? "未知"}</div>
                </div>
              </div>
              <div className="mt-4 rounded-md border border-gray-100 p-3">
                <div className="text-sm font-semibold text-gray-900">关系解释</div>
                <div className="mt-1 text-sm leading-6 text-gray-600">
                  {selectedEdgeEvidenceText || `当前关系表示两个知识点在课程资料中存在“${relationLabelText(getEdgeLabel(selectedEdge))}”联系。后续可以由教师审核或由模型补全更细的因果、先修、组成说明。`}
                </div>
                <div className="mt-2 text-xs text-gray-400">
                  来源：{provenanceSummary({ ...(selectedEdge.provenance || {}), ...(selectedEdge.sourceSpan || {}), ...(selectedEdge.sourceSummary || {}) })}
                </div>
              </div>
              {selectedEdgeEvidenceItems.length > 0 && (
                <div className="mt-4 rounded-md border border-teal-100 bg-teal-50/40 p-3">
                  <div className="text-sm font-semibold text-gray-900">关系证据定位</div>
                  <div className="mt-2 space-y-2">
                    {selectedEdgeEvidenceItems.map((item, index) => {
                      const bbox = formatBBox(item.bbox);
                      const preview = compactText(item.formula_latex || item.table_markdown || item.ocr_text, 110);
                      const loading = evidenceLoadingKey === `edge:${selectedEdge.id}:${index}`;
                      return (
                        <button
                          key={`${String(item.item_id || item.atomic_id || index)}-${index}`}
                          type="button"
                          onClick={() => void openEvidencePanel("edge", selectedEdge.id, index)}
                          className="w-full rounded-md bg-white p-2 text-left text-xs leading-5 text-gray-600 ring-1 ring-transparent hover:ring-teal-200"
                        >
                          <div className="font-medium text-gray-800">
                            {formatType(String(item.modality || "content"))}
                            {item.page !== undefined ? ` · 第 ${String(item.page)} 页` : ""}
                            {bbox ? ` · bbox: ${bbox}` : ""}
                            {loading ? " · 解析中..." : ""}
                          </div>
                          {preview && <div className="mt-1 text-gray-500">{preview}</div>}
                          {(item.image_path || item.source_path) && (
                            <div className="mt-1 truncate text-teal-700">{String(item.image_path || item.source_path)}</div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">关系来源</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedEdge.sourceSpan)}
                </pre>
              </details>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium text-gray-700">Provenance</summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-5 text-gray-100">
                  {serializeSmallJson(selectedEdge.provenance)}
                </pre>
              </details>
            </div>
          ) : (
            <div className="flex h-full min-h-[220px] flex-col justify-center text-sm text-gray-500">
              <i className="ri-cursor-line mb-3 text-3xl text-gray-300"></i>
              <div className="font-medium text-gray-700">选择一个节点或关系</div>
              <div className="mt-2 leading-6">点击节点可查看描述、证据强度与来源；滚轮缩放，拖动画布平移。</div>
            </div>
          )}

          {(evidencePanel || evidenceError) && (
            <div className="mt-4 rounded-md border border-teal-100 bg-white p-3 text-xs leading-5 text-gray-600 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-gray-900">证据解析</div>
                <button
                  type="button"
                  onClick={() => {
                    setEvidencePanel(null);
                    setEvidenceError(null);
                  }}
                  className="text-gray-400 hover:text-gray-700"
                >
                  关闭
                </button>
              </div>
              {evidenceError ? (
                <div className="mt-2 rounded-md bg-amber-50 p-2 text-amber-700">{evidenceError}</div>
              ) : evidencePanel ? (
                <div className="mt-2 space-y-2">
                  {evidencePanel.material && (
                    <div className="rounded-md bg-gray-50 p-2">
                      <div className="font-medium text-gray-800">{evidencePanel.material.title || evidencePanel.material.fileName}</div>
                      <div className="mt-1 text-gray-500">
                        {evidencePanel.material.fileName}
                        {evidencePanel.locator?.page !== undefined && evidencePanel.locator?.page !== null
                          ? ` · 第 ${String(evidencePanel.locator.page)} 页`
                          : ""}
                        {evidencePanel.locator?.bbox ? ` · bbox: ${formatBBox(evidencePanel.locator.bbox)}` : ""}
                      </div>
                    </div>
                  )}
                  {evidencePanel.content?.textExcerpt && (
                    <div className="rounded-md bg-teal-50/60 p-2 text-gray-700">{evidencePanel.content.textExcerpt}</div>
                  )}
                  {(evidencePanel.asset?.imagePathPreview || evidencePanel.asset?.sourcePathPreview) && (
                    <div className="rounded-md bg-gray-50 p-2 text-gray-500">
                      {evidencePanel.asset.imagePathPreview && <div>图片：{evidencePanel.asset.imagePathPreview}</div>}
                      {evidencePanel.asset.sourcePathPreview && <div>来源：{evidencePanel.asset.sourcePathPreview}</div>}
                    </div>
                  )}
                  {(evidenceObjectLoading || evidenceObjectError || evidenceObject) && (
                    <div className="rounded-md border border-gray-100 bg-gray-50 p-2">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <div className="font-medium text-gray-800">原文定位预览</div>
                        {evidencePanel.status?.viewerReady && (
                          <span className="rounded-full bg-teal-50 px-2 py-0.5 text-[11px] text-teal-700">已接入证据源</span>
                        )}
                      </div>
                      {evidenceObjectLoading && <div className="text-gray-500">正在加载原文...</div>}
                      {evidenceObjectError && <div className="rounded bg-amber-50 p-2 text-amber-700">{evidenceObjectError}</div>}
                      {evidenceObject && (
                        evidenceObject.source === "asset" || evidenceObject.contentType.startsWith("image/") ? (
                          <div className="relative overflow-hidden rounded border border-gray-200 bg-white">
                            <img src={evidenceObject.url} alt="证据图片" className="max-h-72 w-full object-contain" />
                            {normalizedBBoxStyle(evidencePanel.locator?.bbox) && (
                              <div
                                className="pointer-events-none absolute border-2 border-rose-500 bg-rose-500/10 shadow-[0_0_0_9999px_rgba(15,23,42,0.08)]"
                                style={normalizedBBoxStyle(evidencePanel.locator?.bbox) || undefined}
                              />
                            )}
                          </div>
                        ) : evidenceObject.contentType.includes("pdf") || evidencePanel.material?.fileType === "pdf" ? (
                          <iframe
                            title="证据原文"
                            src={evidenceObject.url}
                            className="h-72 w-full rounded border border-gray-200 bg-white"
                          />
                        ) : (
                          <a href={evidenceObject.url} target="_blank" rel="noreferrer" className="text-teal-700 hover:text-teal-800">
                            在新窗口打开原文
                          </a>
                        )
                      )}
                      {evidencePanel.locator?.bbox && !normalizedBBoxStyle(evidencePanel.locator.bbox) && (
                        <div className="mt-2 text-[11px] text-gray-400">
                          当前 bbox 不是归一化坐标，已展示坐标值，暂不叠加高亮框。
                        </div>
                      )}
                    </div>
                  )}
                  {evidencePanel.material?.previewUrl && (
                    <a
                      href={evidencePanel.material.previewUrl}
                      className="inline-flex items-center text-teal-700 hover:text-teal-800"
                    >
                      打开资料预览
                    </a>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
