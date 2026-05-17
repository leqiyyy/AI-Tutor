import type { ReactNode } from "react";
import type { AiMessageSource } from "@/types/ai";

interface AiMarkdownContentProps {
  content: string;
  sources?: AiMessageSource[];
  onCitationClick?: (source: AiMessageSource, index: number) => void;
}

type Block =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "table"; rows: string[][]; header: boolean }
  | { type: "code"; text: string };

function citationMap(sources?: AiMessageSource[]) {
  const map = new Map<number, AiMessageSource>();
  for (const source of sources || []) {
    if (typeof source.citationIndex === "number" && !map.has(source.citationIndex)) {
      map.set(source.citationIndex, source);
    }
  }
  return map;
}

function compactEvidence(value?: string, maxLength = 220) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function citationTitle(source: AiMessageSource | undefined, citationIndex: number) {
  if (!source) return `引用 ${citationIndex}`;
  const page = source.page ? ` · 第 ${source.page} 页` : "";
  const evidence = compactEvidence(
    source.snippet || source.rawText || source.ocrText || source.tableMarkdown || source.formulaLatex,
  );
  return evidence
    ? `${source.name}${page}\n${evidence}`
    : `${source.name}${page}`;
}

function renderInline(
  text: string,
  keyPrefix: string,
  citations: Map<number, AiMessageSource>,
  onCitationClick?: (source: AiMessageSource, index: number) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${match.index}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      const citation = /^\[(\d+)\]$/.exec(token);
      if (citation) {
        const citationIndex = Number(citation[1]);
        const source = citations.get(citationIndex);
        nodes.push(
          <button
            key={`${keyPrefix}-r-${match.index}`}
            type="button"
            disabled={!source}
            title={citationTitle(source, citationIndex)}
            onClick={() => source && onCitationClick?.(source, citationIndex)}
            className={`mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded border px-1 text-[11px] font-semibold align-baseline ${
              source
                ? "border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100 cursor-pointer"
                : "border-gray-200 bg-gray-50 text-gray-400 cursor-default"
            }`}
          >
            {citationIndex}
          </button>,
        );
      } else {
      nodes.push(
        <code key={`${keyPrefix}-c-${match.index}`} className="rounded bg-gray-100 px-1 py-0.5 text-[0.92em] text-gray-700">
          {token.slice(1, -1)}
        </code>,
      );
      }
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function isTableLine(line: string) {
  const stripped = line.trim();
  return stripped.includes("|") && stripped.split("|").filter(cell => cell.trim()).length >= 2;
}

function isTableSeparator(line: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function parseTableRow(line: string) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
}

function stripTrailingReferences(content: string) {
  const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
  const start = lines.findIndex(line => /^#{1,6}\s*references\s*$/i.test(line.trim()));
  if (start < 0) return lines.join("\n");
  const tail = lines.slice(start + 1).filter(line => line.trim());
  const referencesOnly = tail.every(line => /^[-*]?\s*\[\d+\]\s+/.test(line.trim()));
  return referencesOnly ? lines.slice(0, start).join("\n").trimEnd() : lines.join("\n");
}

function parseBlocks(content: string): Block[] {
  const lines = stripTrailingReferences(content).replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      index += index < lines.length ? 1 : 0;
      blocks.push({ type: "code", text: codeLines.join("\n") });
      continue;
    }

    if (/^-{3,}$/.test(trimmed)) {
      index += 1;
      continue;
    }

    const heading = /^(#{1,6})\s*(.+)$/.exec(trimmed);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }

    if (isTableLine(line) && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const rows = [parseTableRow(line)];
      index += 2;
      while (index < lines.length && isTableLine(lines[index])) {
        rows.push(parseTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ type: "table", rows, header: true });
      continue;
    }

    const listMatch = /^(\d+\.\s+|[-*]\s+)(.+)$/.exec(trimmed);
    if (listMatch) {
      const ordered = /^\d+\./.test(listMatch[1]);
      const items: string[] = [];
      while (index < lines.length) {
        const itemMatch = /^(\d+\.\s+|[-*]\s+)(.+)$/.exec(lines[index].trim());
        if (!itemMatch || /^\d+\./.test(itemMatch[1]) !== ordered) break;
        items.push(itemMatch[2]);
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,6})\s*/.test(lines[index].trim()) &&
      !/^(\d+\.\s+|[-*]\s+)/.test(lines[index].trim()) &&
      !lines[index].trim().startsWith("```") &&
      !(isTableLine(lines[index]) && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraphLines.join(" ") });
  }

  return blocks;
}

export function AiMarkdownContent({ content, sources, onCitationClick }: AiMarkdownContentProps) {
  const blocks = parseBlocks(content);
  const citations = citationMap(sources);

  return (
    <div className="ai-markdown-content space-y-2 text-sm leading-relaxed">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = block.level <= 2 ? "h3" : "h4";
          return (
            <Tag key={index} className="mt-2 first:mt-0 text-sm font-semibold text-gray-900">
              {renderInline(block.text, `h-${index}`, citations, onCitationClick)}
            </Tag>
          );
        }
        if (block.type === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return (
            <Tag key={index} className={`${block.ordered ? "list-decimal" : "list-disc"} space-y-1 pl-5`}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item, `l-${index}-${itemIndex}`, citations, onCitationClick)}</li>
              ))}
            </Tag>
          );
        }
        if (block.type === "table") {
          const [header, ...body] = block.rows;
          return (
            <div key={index} className="max-w-full overflow-x-auto rounded-md border border-gray-200 bg-white">
              <table className="min-w-full border-collapse text-left text-xs">
                {block.header && (
                  <thead className="bg-gray-50 text-gray-700">
                    <tr>
                      {header.map((cell, cellIndex) => (
                        <th key={cellIndex} className="border-b border-gray-200 px-2.5 py-2 font-semibold">
                          {renderInline(cell, `th-${index}-${cellIndex}`, citations, onCitationClick)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {(block.header ? body : block.rows).map((row, rowIndex) => (
                    <tr key={rowIndex} className="border-t border-gray-100 first:border-t-0">
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="px-2.5 py-2 align-top text-gray-700">
                          {renderInline(cell, `td-${index}-${rowIndex}-${cellIndex}`, citations, onCitationClick)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === "code") {
          return (
            <pre key={index} className="overflow-x-auto rounded-md bg-gray-900 px-3 py-2 text-xs text-gray-100">
              <code>{block.text}</code>
            </pre>
          );
        }
        return (
          <p key={index} className="leading-relaxed">
            {renderInline(block.text, `p-${index}`, citations, onCitationClick)}
          </p>
        );
      })}
    </div>
  );
}
