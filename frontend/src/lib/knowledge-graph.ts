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

export function normalizeKnowledgeGraph(
  data: KnowledgeGraphData,
): Required<Pick<KnowledgeGraphData, "nodes" | "edges">> &
  Omit<KnowledgeGraphData, "nodes" | "edges"> {
  const nodes = data.nodes.map((node) => ({
    ...node,
    parent: node.parent ?? null,
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const fallbackEdges = buildFallbackEdges(nodes);
  const rawEdges = data.edges && data.edges.length > 0 ? data.edges : fallbackEdges;
  const edges = rawEdges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge, index) => ({
      ...edge,
      id: edge.id || `edge-${edge.source}-${edge.target}-${index}`,
    }));

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
): { nodes: KnowledgeGraphNode[]; edges: KnowledgeGraphEdge[] } {
  const normalized = normalizeKnowledgeGraph(data);
  const rootIds = getKnowledgeGraphRootIds(normalized);
  const expanded = new Set(expandedNodeIds);
  const visibleNodeIds = new Set(rootIds);

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
    });
  }

  return {
    nodes: normalized.nodes.filter((node) => visibleNodeIds.has(node.id)),
    edges: normalized.edges.filter(
      (edge) =>
        visibleNodeIds.has(edge.source) &&
        visibleNodeIds.has(edge.target) &&
        expanded.has(edge.source),
    ),
  };
}
