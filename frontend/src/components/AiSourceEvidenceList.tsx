import { useEffect, useRef, useState } from "react";
import { courseService, downloadCourseFileFromUrl, fetchAuthenticatedObjectUrl } from "@/services/course";
import type { AiMessageSource } from "@/types/ai";
import type { TeacherCourseMaterialPreviewData } from "@/types/course";

interface AiSourceEvidenceListProps {
  sources: AiMessageSource[];
  wide?: boolean;
  courseId?: string;
  role?: "student" | "teacher";
}

function sourceIconClass(type?: string, modality?: string) {
  const value = `${type || ""} ${modality || ""}`.toLowerCase();
  if (value.includes("image") || value.includes("figure")) return "ri-image-line text-sky-500";
  if (value.includes("table")) return "ri-table-line text-emerald-500";
  if (value.includes("formula") || value.includes("equation")) return "ri-function-line text-violet-500";
  if (value.includes("pdf")) return "ri-file-pdf-2-line text-rose-500";
  if (value.includes("ppt")) return "ri-slideshow-line text-orange-500";
  if (value.includes("word") || value.includes("doc")) return "ri-file-word-line text-blue-500";
  return "ri-file-text-line text-teal-500";
}

function compactText(value?: string, maxLength = 520) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function evidenceText(source: AiMessageSource) {
  return compactText(
    source.snippet ||
      source.rawText ||
      source.ocrText ||
      source.tableMarkdown ||
      source.formulaLatex,
  );
}

function formatScore(source: AiMessageSource) {
  const score = source.relevanceScore ?? source.rerankScore ?? source.retrievalScore ?? source.score;
  if (typeof score !== "number" || !Number.isFinite(score)) return "";
  if (score >= 0 && score <= 1) return `${Math.round(score * 100)}%`;
  return score.toFixed(score >= 10 ? 0 : 2);
}

function formatBBox(bbox: unknown) {
  if (!bbox) return "";
  if (Array.isArray(bbox)) return bbox.slice(0, 4).map(item => String(item)).join(", ");
  if (typeof bbox === "object") return JSON.stringify(bbox);
  return String(bbox);
}

function isNonPagedSource(source: AiMessageSource) {
  const value = `${source.name || ""} ${source.type || ""} ${source.modality || ""}`.toLowerCase();
  return /\.(md|markdown|txt|csv|json|html?)\b/.test(value)
    || value.includes("markdown")
    || value.includes("text/plain");
}

type PreviewState = {
  loading?: boolean;
  error?: string;
  data?: TeacherCourseMaterialPreviewData;
};

type AssetPreviewState = {
  loading?: boolean;
  error?: string;
  objectUrl?: string;
  contentType?: string;
};

type MaterialInlinePreviewState = {
  loading?: boolean;
  error?: string;
  objectUrl?: string;
  contentType?: string;
};

export function AiSourceEvidenceList({ sources, wide, courseId, role = "student" }: AiSourceEvidenceListProps) {
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({});
  const [assetPreviews, setAssetPreviews] = useState<Record<string, AssetPreviewState>>({});
  const [materialInlinePreviews, setMaterialInlinePreviews] = useState<Record<string, MaterialInlinePreviewState>>({});
  const [expandedSourceKeys, setExpandedSourceKeys] = useState<Record<string, boolean>>({});
  const [downloadingKey, setDownloadingKey] = useState<string | null>(null);
  const assetObjectUrlsRef = useRef<Set<string>>(new Set());
  const materialObjectUrlsRef = useRef<Set<string>>(new Set());

  useEffect(() => () => {
    assetObjectUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    assetObjectUrlsRef.current.clear();
    materialObjectUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    materialObjectUrlsRef.current.clear();
  }, []);

  const canOpenMaterial = (source: AiMessageSource) => Boolean(courseId && source.materialId);
  const evidenceAssetParams = (source: AiMessageSource) => {
    const metadata = source.metadata || {};
    const itemId = String(metadata.item_id || metadata.itemId || "").trim();
    const atomicId = String(metadata.atomic_id || metadata.atomicId || "").trim();
    const contentIndex = String(metadata.content_index || metadata.contentIndex || "").trim();
    return {
      itemId: itemId || undefined,
      atomicId: atomicId || undefined,
      contentIndex: contentIndex || undefined,
    };
  };
  const canOpenEvidenceAsset = (source: AiMessageSource) => {
    const params = evidenceAssetParams(source);
    return Boolean(canOpenMaterial(source) && (params.itemId || params.atomicId || params.contentIndex));
  };

  const previewSource = async (source: AiMessageSource, key: string) => {
    if (!courseId || !source.materialId) return;
    const existing = previews[key];
    if (existing?.data) {
      setPreviews(prev => ({ ...prev, [key]: {} }));
      return;
    }
    setPreviews(prev => ({ ...prev, [key]: { loading: true } }));
    try {
      const data = role === "teacher"
        ? await courseService.getTeacherCourseMaterialPreview(courseId, source.materialId)
        : await courseService.getStudentCourseMaterialPreview(courseId, source.materialId);
      setPreviews(prev => ({ ...prev, [key]: { data } }));
    } catch (error) {
      setPreviews(prev => ({
        ...prev,
        [key]: { error: error instanceof Error ? error.message : "无法加载资料预览" },
      }));
    }
  };

  const downloadSource = async (source: AiMessageSource, key: string) => {
    if (!courseId || !source.materialId) return;
    setDownloadingKey(key);
    try {
      const result = role === "teacher"
        ? await courseService.downloadTeacherCourseFile(courseId, source.materialId)
        : await courseService.downloadStudentCourseFile(courseId, source.materialId);
      await downloadCourseFileFromUrl(result.downloadUrl, result.fileName);
    } finally {
      setDownloadingKey(null);
    }
  };

  const previewOriginalMaterial = async (source: AiMessageSource, key: string) => {
    if (!courseId || !source.materialId) return;
    const existing = materialInlinePreviews[key];
    if (existing?.objectUrl) {
      URL.revokeObjectURL(existing.objectUrl);
      materialObjectUrlsRef.current.delete(existing.objectUrl);
      setMaterialInlinePreviews(prev => ({ ...prev, [key]: {} }));
      return;
    }
    setMaterialInlinePreviews(prev => ({ ...prev, [key]: { loading: true } }));
    try {
      const viewUrl = courseService.getCourseMaterialViewUrl(role, courseId, source.materialId);
      const result = await fetchAuthenticatedObjectUrl(viewUrl);
      materialObjectUrlsRef.current.add(result.objectUrl);
      setMaterialInlinePreviews(prev => ({ ...prev, [key]: result }));
    } catch (error) {
      setMaterialInlinePreviews(prev => ({
        ...prev,
        [key]: { error: error instanceof Error ? error.message : "无法加载原文件" },
      }));
    }
  };

  const previewEvidenceAsset = async (source: AiMessageSource, key: string) => {
    if (!courseId || !source.materialId) return;
    const existing = assetPreviews[key];
    if (existing?.objectUrl) {
      URL.revokeObjectURL(existing.objectUrl);
      assetObjectUrlsRef.current.delete(existing.objectUrl);
      setAssetPreviews(prev => ({ ...prev, [key]: {} }));
      return;
    }
    setAssetPreviews(prev => ({ ...prev, [key]: { loading: true } }));
    try {
      const assetUrl = courseService.getCourseMaterialEvidenceAssetUrl(
        role,
        courseId,
        source.materialId,
        evidenceAssetParams(source),
      );
      const result = await fetchAuthenticatedObjectUrl(assetUrl);
      assetObjectUrlsRef.current.add(result.objectUrl);
      setAssetPreviews(prev => ({ ...prev, [key]: result }));
    } catch (error) {
      setAssetPreviews(prev => ({
        ...prev,
        [key]: { error: error instanceof Error ? error.message : "无法加载证据原图" },
      }));
    }
  };

  return (
    <div className={wide ? "grid grid-cols-1 gap-3 xl:grid-cols-2" : "space-y-2.5"}>
      {sources.map((source, index) => {
        const evidence = evidenceText(source);
        const score = formatScore(source);
        const bbox = formatBBox(source.bbox);
        const key = `${source.citationIndex ?? index}-${source.chunkId || source.name}-${source.page || 0}`;
        const expanded = Boolean(expandedSourceKeys[key]);
        const showPage = source.page > 0 && !isNonPagedSource(source);

        return (
          <article
            key={key}
            className="rounded-xl border border-gray-100 bg-white/90 p-3 shadow-sm transition-colors hover:border-teal-200 hover:bg-teal-50/40"
          >
            <div className="flex min-w-0 items-start gap-2.5">
              <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gray-50">
                <i className={`text-lg ${sourceIconClass(source.type, source.modality)}`}></i>
              </div>
              <div className="min-w-0 flex-1">
                <div className="break-words text-xs font-semibold leading-snug text-gray-800">
                  {source.name || "课程资料"}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                  {source.citationIndex && (
                    <span className="rounded-full border border-teal-100 bg-teal-50 px-2 py-0.5 font-medium text-teal-700">
                      引用 [{source.citationIndex}]
                    </span>
                  )}
                  {showPage && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">第 {source.page} 页</span>
                  )}
                  {(source.modality || source.type) && (
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">
                      {source.modality || source.type}
                    </span>
                  )}
                  {score && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-700">相关度 {score}</span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setExpandedSourceKeys(prev => ({ ...prev, [key]: !prev[key] }))}
                className="mt-0.5 inline-flex flex-shrink-0 items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:border-teal-200 hover:text-teal-700"
              >
                <i className={expanded ? "ri-arrow-up-s-line" : "ri-arrow-down-s-line"}></i>
                {expanded ? "收起" : "查看引用细节"}
              </button>
            </div>

            {expanded && (
              <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-700">
                {evidence || "该引用暂未返回可展示的片段，但已保留文件、定位和元数据用于后续回溯。"}
              </div>
            )}

            {expanded && canOpenMaterial(source) && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => { void previewSource(source, key); }}
                  className="inline-flex items-center gap-1 rounded-lg border border-teal-100 bg-teal-50 px-2.5 py-1 text-[11px] font-medium text-teal-700 transition-colors hover:bg-teal-100"
                >
                  <i className={previews[key]?.loading ? "ri-loader-4-line animate-spin" : "ri-eye-line"}></i>
                  {previews[key]?.data ? "收起预览" : "预览原资料"}
                </button>
                <button
                  type="button"
                  onClick={() => { void previewOriginalMaterial(source, key); }}
                  className="inline-flex items-center gap-1 rounded-lg border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700 transition-colors hover:bg-indigo-100"
                >
                  <i className={materialInlinePreviews[key]?.loading ? "ri-loader-4-line animate-spin" : "ri-file-search-line"}></i>
                  {materialInlinePreviews[key]?.objectUrl ? "收起原文件" : "查看原文件"}
                </button>
                <button
                  type="button"
                  onClick={() => { void downloadSource(source, key); }}
                  disabled={downloadingKey === key}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:border-teal-200 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <i className={downloadingKey === key ? "ri-loader-4-line animate-spin" : "ri-download-line"}></i>
                  下载原文件
                </button>
                {canOpenEvidenceAsset(source) && (
                  <button
                    type="button"
                    onClick={() => { void previewEvidenceAsset(source, key); }}
                    className="inline-flex items-center gap-1 rounded-lg border border-sky-100 bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700 transition-colors hover:bg-sky-100"
                  >
                    <i className={assetPreviews[key]?.loading ? "ri-loader-4-line animate-spin" : "ri-image-line"}></i>
                    {assetPreviews[key]?.objectUrl ? "收起原图" : "查看原图"}
                  </button>
                )}
              </div>
            )}

            {expanded && previews[key]?.error && (
              <div className="mt-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {previews[key]?.error}
              </div>
            )}

            {expanded && previews[key]?.data && (
              <div className="mt-2 rounded-lg border border-teal-100 bg-white px-3 py-2">
                <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-gray-500">
                  <span>{previews[key]?.data?.previewSource === "original_file" ? "原始文本预览" : "解析文本预览"}</span>
                  {previews[key]?.data?.textTruncated && <span>已截断</span>}
                </div>
                <div className="max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-gray-700">
                  {previews[key]?.data?.textContent || "该资料暂无可预览文本，可下载原文件查看。"}
                </div>
              </div>
            )}

            {expanded && materialInlinePreviews[key]?.error && (
              <div className="mt-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {materialInlinePreviews[key]?.error}
              </div>
            )}

            {expanded && materialInlinePreviews[key]?.objectUrl && (
              <div className="mt-2 rounded-lg border border-indigo-100 bg-white p-2">
                {materialInlinePreviews[key]?.contentType === "application/pdf" ? (
                  <iframe
                    title={`${source.name || "原文件"} 预览`}
                    src={`${materialInlinePreviews[key]?.objectUrl}#page=${source.page > 0 ? source.page : 1}`}
                    className="h-80 w-full rounded-md border border-gray-100"
                  />
                ) : materialInlinePreviews[key]?.contentType?.startsWith("image/") ? (
                  <img
                    src={materialInlinePreviews[key]?.objectUrl}
                    alt={source.name}
                    className="max-h-80 w-full rounded-md object-contain"
                  />
                ) : materialInlinePreviews[key]?.contentType?.startsWith("video/") ? (
                  <video
                    src={materialInlinePreviews[key]?.objectUrl}
                    controls
                    className="max-h-80 w-full rounded-md bg-black"
                  />
                ) : (
                  <a
                    href={materialInlinePreviews[key]?.objectUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium text-indigo-700 hover:text-indigo-800"
                  >
                    <i className="ri-external-link-line"></i>
                    在新窗口打开原文件
                  </a>
                )}
              </div>
            )}

            {expanded && assetPreviews[key]?.error && (
              <div className="mt-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                {assetPreviews[key]?.error}
              </div>
            )}

            {expanded && assetPreviews[key]?.objectUrl && (
              <div className="mt-2 rounded-lg border border-sky-100 bg-white p-2">
                {assetPreviews[key]?.contentType?.startsWith("image/") ? (
                  <img
                    src={assetPreviews[key]?.objectUrl}
                    alt={source.name}
                    className="max-h-72 w-full rounded-md object-contain"
                  />
                ) : (
                  <a
                    href={assetPreviews[key]?.objectUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:text-sky-800"
                  >
                    <i className="ri-external-link-line"></i>
                    打开证据资源
                  </a>
                )}
              </div>
            )}

            {expanded && (source.imagePath || source.sourcePath || bbox || source.chunkId) && (
              <div className="mt-2 space-y-1 text-[11px] leading-relaxed text-gray-500">
                {source.imagePath && <div className="break-all">图片：{source.imagePath}</div>}
                {source.sourcePath && <div className="break-all">文件路径：{source.sourcePath}</div>}
                {bbox && <div className="break-all">区域：{bbox}</div>}
                {source.chunkId && <div className="break-all">Chunk：{source.chunkId}</div>}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
