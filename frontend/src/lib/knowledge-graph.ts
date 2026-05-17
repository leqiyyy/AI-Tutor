import type {
  KnowledgeGraphData,
  KnowledgeGraphEdge,
  KnowledgeGraphNode,
} from "@/types/course";

function buildFallbackEdges(nodes: KnowledgeGraphNode[]): KnowledgeGraphEdge[] {
  return nodes
    .filter((node) => node.parent)
    .map((node) => ({
      id: `edge-${node.parent}-${node.id}`,
      source: node.parent as string,
      target: node.id,
      relationType: "contains",
      color: "#d1d5db",
    }));
}

function canonicalKey(node: KnowledgeGraphNode) {
  const canonical = String(node.canonicalName || "").trim().toLowerCase();
  if (!canonical) return "";
  const type = String(node.type || "").trim().toLowerCase();
  if (["course", "material", "document", "file", "page", "chunk"].includes(type)) {
    return "";
  }
  return `${type || "concept"}:${canonical}`;
}

function mergeArray<T>(left?: T[], right?: T[], limit = 12): T[] | undefined {
  const merged: T[] = [];
  [...(left || []), ...(right || [])].forEach((item) => {
    if (item === undefined || item === null) return;
    const key = typeof item === "object" ? JSON.stringify(item) : String(item);
    if (!merged.some((existing) => (typeof existing === "object" ? JSON.stringify(existing) : String(existing)) === key)) {
      merged.push(item);
    }
  });
  return merged.length > 0 ? merged.slice(0, limit) : undefined;
}

function mergeSourceSpan(
  left?: Record<string, unknown>,
  right?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  if (!left && !right) return undefined;
  const merged: Record<string, unknown> = { ...(left || {}), ...(right || {}) };
  const leftEvidence = Array.isArray(left?.evidence_items) ? left?.evidence_items as unknown[] : [];
  const rightEvidence = Array.isArray(right?.evidence_items) ? right?.evidence_items as unknown[] : [];
  const evidence = mergeArray(leftEvidence, rightEvidence, 10);
  if (evidence) merged.evidence_items = evidence;
  const chunkIds = mergeArray(
    Array.isArray(left?.chunk_ids) ? left?.chunk_ids as string[] : [],
    Array.isArray(right?.chunk_ids) ? right?.chunk_ids as string[] : [],
    20,
  );
  if (chunkIds) merged.chunk_ids = chunkIds;
  return merged;
}

function mergeGraphNodes(nodes: KnowledgeGraphNode[]) {
  const mergedNodes: KnowledgeGraphNode[] = [];
  const idMap = new Map<string, string>();
  const byCanonical = new Map<string, KnowledgeGraphNode>();

  nodes.forEach((node) => {
    const key = canonicalKey(node);
    if (!key) {
      mergedNodes.push(node);
      idMap.set(node.id, node.id);
      return;
    }

    const existing = byCanonical.get(key);
    if (!existing) {
      const normalizedNode = {
        ...node,
        label: node.canonicalName || node.label,
        aliases: mergeArray(node.aliases || [], node.label && node.label !== node.canonicalName ? [node.label] : [], 12) || node.aliases,
      };
      byCanonical.set(key, normalizedNode);
      mergedNodes.push(normalizedNode);
      idMap.set(node.id, normalizedNode.id);
      return;
    }

    idMap.set(node.id, existing.id);
    existing.aliases = mergeArray(existing.aliases || [], node.aliases || [], 12);
    if (node.label && node.label !== existing.label) {
      existing.aliases = mergeArray(existing.aliases || [], [node.label], 12);
    }
    existing.confidence = Math.max(existing.confidence ?? 0, node.confidence ?? 0);
    existing.masteryEvidenceCount = Math.max(existing.masteryEvidenceCount ?? 0, node.masteryEvidenceCount ?? 0);
    existing.sourceSpan = mergeSourceSpan(existing.sourceSpan, node.sourceSpan);
    existing.provenance = { ...(existing.provenance || {}), ...(node.provenance || {}) };
    if (!existing.summary && node.summary) existing.summary = node.summary;
    if (!existing.description && node.description) existing.description = node.description;
  });

  return { nodes: mergedNodes, idMap };
}

function mergeGraphEdges(edges: KnowledgeGraphEdge[]) {
  const merged = new Map<string, KnowledgeGraphEdge>();
  edges.forEach((edge) => {
    if (edge.source === edge.target) return;
    const key = `${edge.source}->${edge.target}:${edge.relationType || edge.label || "related_to"}`;
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, edge);
      return;
    }
    existing.confidence = Math.max(existing.confidence ?? 0, edge.confidence ?? 0);
    existing.weight = Math.max(existing.weight ?? 0, edge.weight ?? 0);
    existing.sourceSpan = mergeSourceSpan(existing.sourceSpan, edge.sourceSpan);
    existing.provenance = { ...(existing.provenance || {}), ...(edge.provenance || {}) };
    if (!existing.description && edge.description) existing.description = edge.description;
  });
  return Array.from(merged.values());
}

export function normalizeKnowledgeGraph(
  data: KnowledgeGraphData,
): Required<Pick<KnowledgeGraphData, "nodes" | "edges">> &
  Omit<KnowledgeGraphData, "nodes" | "edges"> {
  const rawNodes = data.nodes.map((node) => ({
    ...node,
    parent: node.parent ?? null,
  }));
  const { nodes, idMap } = mergeGraphNodes(rawNodes);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const fallbackEdges = buildFallbackEdges(nodes);
  const rawEdges = data.edges && data.edges.length > 0 ? data.edges : fallbackEdges;
  const edges = mergeGraphEdges(rawEdges
    .map((edge) => ({
      ...edge,
      source: idMap.get(edge.source) || edge.source,
      target: idMap.get(edge.target) || edge.target,
    }))
    .filter((edge) => edge.source !== edge.target && nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge, index) => ({
      ...edge,
      id: edge.id || `edge-${edge.source}-${edge.target}-${index}`,
    })));

  return {
    ...data,
    nodes,
    edges,
  };
}

export function getKnowledgeGraphRootIds(data: KnowledgeGraphData): string[] {
  const normalized = normalizeKnowledgeGraph(data);
  const explicitRootId = normalized.meta?.rootNodeId;

  if (
    explicitRootId &&
    normalized.nodes.some((node) => node.id === explicitRootId)
  ) {
    return [explicitRootId];
  }

  const incomingTargets = new Set(normalized.edges.map((edge) => edge.target));
  const rootIds = normalized.nodes
    .filter((node) => node.parent === null || !incomingTargets.has(node.id))
    .map((node) => node.id);

  if (rootIds.length > 0) {
    return Array.from(new Set(rootIds));
  }

  return normalized.nodes[0] ? [normalized.nodes[0].id] : [];
}

export function getVisibleKnowledgeGraph(
  data: KnowledgeGraphData,
  expandedNodeIds: string[],
  options: { undirected?: boolean } = {},
): { nodes: KnowledgeGraphNode[]; edges: KnowledgeGraphEdge[] } {
  const normalized = normalizeKnowledgeGraph(data);
  const rootIds = getKnowledgeGraphRootIds(normalized);
  const expanded = new Set(expandedNodeIds);
  const visibleNodeIds = new Set(rootIds);
  const undirected = options.undirected ?? false;

  let hasChanges = true;
  while (hasChanges) {
    hasChanges = false;

    normalized.edges.forEach((edge) => {
      if (
        visibleNodeIds.has(edge.source) &&
        expanded.has(edge.source) &&
        !visibleNodeIds.has(edge.target)
      ) {
        visibleNodeIds.add(edge.target);
        hasChanges = true;
      }
      if (
        undirected &&
        visibleNodeIds.has(edge.target) &&
        expanded.has(edge.target) &&
        !visibleNodeIds.has(edge.source)
      ) {
        visibleNodeIds.add(edge.source);
        hasChanges = true;
      }
    });
  }

  return {
    nodes: normalized.nodes.filter((node) => visibleNodeIds.has(node.id)),
    edges: normalized.edges.filter(
      (edge) =>
        visibleNodeIds.has(edge.source) &&
        visibleNodeIds.has(edge.target) &&
        (expanded.has(edge.source) || (undirected && expanded.has(edge.target))),
    ),
  };
}

export function getKnowledgeGraphNeighborIds(
  edges: KnowledgeGraphEdge[],
  nodeId: string,
  options: { undirected?: boolean } = {},
): string[] {
  const neighborIds = new Set<string>();
  edges.forEach((edge) => {
    if (edge.source === nodeId) {
      neighborIds.add(edge.target);
    }
    if (options.undirected && edge.target === nodeId) {
      neighborIds.add(edge.source);
    }
  });
  return Array.from(neighborIds);
}
