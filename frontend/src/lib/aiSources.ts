import type { AiMessageSource } from "@/types/ai";

export type AiSourceFileSummary = {
  key: string;
  name: string;
  type: string;
  pages: number[];
  count: number;
};

export function summarizeSourcesByFile(
  sources: AiMessageSource[] | undefined,
): AiSourceFileSummary[] {
  const byFile = new Map<string, AiSourceFileSummary>();

  for (const source of sources ?? []) {
    const name = normalizeSourceName(source.name);
    const key = `${source.materialId || ""}:${name.toLowerCase()}`;
    const current = byFile.get(key) ?? {
      key,
      name,
      type: source.type || "document",
      pages: [],
      count: 0,
    };

    if (source.page > 0 && !current.pages.includes(source.page)) {
      current.pages.push(source.page);
    }
    current.count += 1;
    byFile.set(key, current);
  }

  return [...byFile.values()].map((item) => ({
    ...item,
    pages: item.pages.sort((a, b) => a - b),
  }));
}

export function formatSourceFilePages(pages: number[]) {
  if (pages.length === 0) return "";
  const shown = pages.slice(0, 3).map((page) => `P${page}`).join("、");
  return pages.length > 3 ? `${shown} 等` : shown;
}

export function compactSourceFileName(name: string, maxLength = 18) {
  if (name.length <= maxLength) return name;
  return `${name.slice(0, Math.max(1, maxLength - 1))}…`;
}

function normalizeSourceName(name: string | undefined) {
  const text = (name || "课程资料").replace(/\s+/g, " ").trim();
  return text || "课程资料";
}
