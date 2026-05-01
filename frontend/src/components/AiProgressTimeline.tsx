import type { AiProgressEvent } from "@/types/ai";

interface AiProgressTimelineProps {
  steps: AiProgressEvent[];
}

function progressElapsed(step?: AiProgressEvent) {
  return step?.elapsedMs ?? step?.elapsed_ms;
}

function formatElapsed(ms?: number) {
  if (typeof ms !== "number" || Number.isNaN(ms)) return "";
  return `${(ms / 1000).toFixed(2)}s`;
}

function stepIconClass(status: AiProgressEvent["status"]) {
  if (status === "done") return "ri-checkbox-circle-fill text-teal-600";
  if (status === "error") return "ri-close-circle-fill text-red-500";
  return "ri-loader-4-line animate-spin text-blue-600";
}

const DISPLAY_STEPS: Record<string, string> = {
  understand: "理解问题",
  prepare: "准备资料",
  retrieve: "查找依据",
  answer: "生成回答",
};

function displayStage(stage: string) {
  if (["request_received", "conversation_context", "message_saved", "question_route", "query_rewrite", "effective_query"].includes(stage)) {
    return "understand";
  }
  if (["rag_prepare", "attachments", "knowledge_base", "query_engine_ready", "aquery_history"].includes(stage)) {
    return "prepare";
  }
  if (["rag_query", "official_retrieval", "evidence_prepare", "rerank"].includes(stage)) {
    return "retrieve";
  }
  if (["direct_answer", "direct_generation", "answer_repair", "persist_answer", "completed"].includes(stage)) {
    return "answer";
  }
  return "prepare";
}

function compactProgress(steps: AiProgressEvent[]) {
  const byStage = new Map<string, AiProgressEvent>();
  steps.forEach((step) => {
    const stage = displayStage(step.stage);
    const existing = byStage.get(stage);
    byStage.set(stage, {
      ...existing,
      ...step,
      stage,
      label: step.status === "error" ? step.label : DISPLAY_STEPS[stage],
      status: step.status,
    });
  });
  return ["understand", "prepare", "retrieve", "answer"]
    .map((stage) => byStage.get(stage))
    .filter(Boolean) as AiProgressEvent[];
}

export function AiProgressTimeline({ steps }: AiProgressTimelineProps) {
  const visibleSteps = steps.length
    ? compactProgress(steps)
    : [
        {
          stage: "waiting",
          status: "running" as const,
          label: "正在启动 AI 助教",
        },
      ];
  const lastElapsed = progressElapsed(visibleSteps[visibleSteps.length - 1]);

  return (
    <div className="w-full max-w-[520px] rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2.5 text-xs text-gray-700">
      <div className="space-y-2">
        {visibleSteps.slice(-8).map((step) => (
          <div key={step.stage} className="grid grid-cols-[18px_1fr_auto] items-center gap-2">
            <i className={`${stepIconClass(step.status)} text-sm leading-none`}></i>
            <span className="min-w-0 truncate">{step.label}</span>
            <span className="tabular-nums text-gray-400">{formatElapsed(progressElapsed(step))}</span>
          </div>
        ))}
      </div>
      {typeof lastElapsed === "number" && (
        <div className="mt-2 inline-flex items-center gap-1 rounded-md bg-white/80 px-2 py-1 text-blue-700">
          <i className="ri-sparkling-2-line text-xs"></i>
          <span>运行中 {formatElapsed(lastElapsed)}</span>
        </div>
      )}
    </div>
  );
}
