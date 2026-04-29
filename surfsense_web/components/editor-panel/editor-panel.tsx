"use client";

import { FindReplacePlugin } from "@platejs/find-replace";
import { useAtomValue, useSetAtom } from "jotai";
import {
	Check,
	Copy,
	Download,
	FileQuestionMark,
	FileText,
	Pencil,
	RefreshCw,
	XIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { pendingChunkHighlightAtom } from "@/atoms/document-viewer/pending-chunk-highlight.atom";
import { closeEditorPanelAtom, editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { VersionHistoryButton } from "@/components/documents/version-history";
import type { PlateEditorInstance } from "@/components/editor/plate-editor";
import { SourceCodeEditor } from "@/components/editor/source-code-editor";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { CITATION_HIGHLIGHT_CLASS } from "@/components/ui/search-highlight-node";
import { Spinner } from "@/components/ui/spinner";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { authenticatedFetch, getBearerToken, redirectToLogin } from "@/lib/auth-utils";
import { buildCitationSearchCandidates } from "@/lib/citation-search";
import { inferMonacoLanguageFromPath } from "@/lib/editor-language";

const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((m) => ({ default: m.PlateEditor })),
	{ ssr: false, loading: () => <EditorPanelSkeleton /> }
);

type CitationHighlightStatus = "exact" | "miss";

const LARGE_DOCUMENT_THRESHOLD = 2 * 1024 * 1024; // 2MB
const CITATION_MAX_LENGTH = 16 * 1024 * 1024; // 16MB on-demand cap for citation jumps

interface EditorContent {
	document_id: number;
	title: string;
	document_type?: string;
	source_markdown: string;
	content_size_bytes?: number;
	chunk_count?: number;
	truncated?: boolean;
}

const EDITABLE_DOCUMENT_TYPES = new Set(["FILE", "NOTE"]);
type EditorRenderMode = "rich_markdown" | "source_code";

type AgentFilesystemMount = {
	mount: string;
	rootPath: string;
};

function normalizeLocalVirtualPathForEditor(
	candidatePath: string,
	mounts: AgentFilesystemMount[]
): string {
	const normalizedCandidate = candidatePath.trim().replace(/\\/g, "/").replace(/\/+/g, "/");
	if (!normalizedCandidate) return candidatePath;
	const defaultMount = mounts[0]?.mount;
	if (!defaultMount) {
		return normalizedCandidate.startsWith("/")
			? normalizedCandidate
			: `/${normalizedCandidate.replace(/^\/+/, "")}`;
	}

	const mountNames = new Set(mounts.map((entry) => entry.mount));
	if (normalizedCandidate.startsWith("/")) {
		const relative = normalizedCandidate.replace(/^\/+/, "");
		const [firstSegment] = relative.split("/", 1);
		if (mountNames.has(firstSegment)) {
			return `/${relative}`;
		}
		return `/${defaultMount}/${relative}`;
	}

	const relative = normalizedCandidate.replace(/^\/+/, "");
	const [firstSegment] = relative.split("/", 1);
	if (mountNames.has(firstSegment)) {
		return `/${relative}`;
	}
	return `/${defaultMount}/${relative}`;
}

function EditorPanelSkeleton() {
	return (
		<div className="space-y-6 p-6">
			<div className="h-6 w-3/4 rounded-md bg-muted/60 animate-pulse" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse" />
				<div className="h-3 w-[95%] rounded-md bg-muted/60 animate-pulse [animation-delay:100ms]" />
				<div className="h-3 w-[88%] rounded-md bg-muted/60 animate-pulse [animation-delay:200ms]" />
				<div className="h-3 w-[60%] rounded-md bg-muted/60 animate-pulse [animation-delay:300ms]" />
			</div>
			<div className="h-5 w-2/5 rounded-md bg-muted/60 animate-pulse [animation-delay:400ms]" />
			<div className="space-y-2.5">
				<div className="h-3 w-full rounded-md bg-muted/60 animate-pulse [animation-delay:500ms]" />
				<div className="h-3 w-[92%] rounded-md bg-muted/60 animate-pulse [animation-delay:600ms]" />
				<div className="h-3 w-[75%] rounded-md bg-muted/60 animate-pulse [animation-delay:700ms]" />
			</div>
		</div>
	);
}

export function EditorPanelContent({
	kind = "document",
	documentId,
	localFilePath,
	searchSpaceId,
	title,
	onClose,
}: {
	kind?: "document" | "local_file";
	documentId?: number;
	localFilePath?: string;
	searchSpaceId?: number;
	title: string | null;
	onClose?: () => void;
}) {
	const electronAPI = useElectronAPI();
	const [editorDoc, setEditorDoc] = useState<EditorContent | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);
	const [downloading, setDownloading] = useState(false);
	const [isEditing, setIsEditing] = useState(false);

	const [editedMarkdown, setEditedMarkdown] = useState<string | null>(null);
	const [localFileContent, setLocalFileContent] = useState("");
	const [hasCopied, setHasCopied] = useState(false);
	const markdownRef = useRef<string>("");
	const copyResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const initialLoadDone = useRef(false);
	const changeCountRef = useRef(0);
	const [displayTitle, setDisplayTitle] = useState(title || "Untitled");
	const isLocalFileMode = kind === "local_file";
	const editorRenderMode: EditorRenderMode = isLocalFileMode ? "source_code" : "rich_markdown";

	// --- Citation-jump highlight wiring ----------------------------------
	// `EditorPanelContent` is the consumer of `pendingChunkHighlightAtom`: when
	// a citation badge is clicked, the badge stages `{documentId, chunkId,
	// chunkText}` and opens this panel. We drive Plate's `FindReplacePlugin`
	// (registered in every preset) to highlight the cited text natively via
	// Slate decorations — no DOM walking, no Range gymnastics. The state
	// machine below escalates the document fetch from 2MB → 16MB once if no
	// candidate snippet matched in the preview, and surfaces miss outcomes
	// via an inline alert.
	const pending = useAtomValue(pendingChunkHighlightAtom);
	const setPendingHighlight = useSetAtom(pendingChunkHighlightAtom);
	const [fetchKey, setFetchKey] = useState(0);
	const [maxLengthOverride, setMaxLengthOverride] = useState<number | null>(null);
	const [highlightResult, setHighlightResult] = useState<CitationHighlightStatus | null>(null);
	const editorRef = useRef<PlateEditorInstance | null>(null);
	const escalatedForRef = useRef<number | null>(null);
	const lastAppliedChunkIdRef = useRef<number | null>(null);
	// Tracks whether a citation highlight is currently decorated in the
	// editor. We use a ref (not state) because the click-to-dismiss handler
	// runs in a stable callback that would otherwise close over stale state.
	const isHighlightActiveRef = useRef(false);
	// Once a citation jump targets this doc we have to keep `PlateEditor`
	// mounted for the *rest of the doc session* — even after the highlight
	// effect clears `pendingChunkHighlightAtom` (which it does as soon as
	// the decoration is applied, so a follow-up citation on the same chunk
	// can re-trigger). Without this latch, non-editable docs would re-render
	// back into `MarkdownViewer` the instant `pending` is released, tearing
	// down the Plate decorations and dropping the highlight after a frame.
	const [stickyPlateMode, setStickyPlateMode] = useState(false);

	const clearCitationSearch = useCallback(() => {
		isHighlightActiveRef.current = false;
		const editor = editorRef.current;
		if (!editor) return;
		try {
			editor.setOption(FindReplacePlugin, "search", "");
			editor.api.redecorate();
		} catch (err) {
			console.warn("[EditorPanelContent] clearCitationSearch failed:", err);
		}
	}, []);

	// Dismiss the highlight when the user interacts with the editor surface.
	// `onPointerDown` fires before focus / selection changes so the click
	// itself feels responsive — the highlight clears in the same event tick
	// that places the cursor. No-op when nothing is highlighted, so we don't
	// thrash `redecorate` on every click in normal editing.
	const handleEditorPointerDown = useCallback(() => {
		if (!isHighlightActiveRef.current) return;
		clearCitationSearch();
		setHighlightResult(null);
	}, [clearCitationSearch]);

	const isCitationTarget = !!pending && !isLocalFileMode && pending.documentId === documentId;
	const resolveLocalVirtualPath = useCallback(
		async (candidatePath: string): Promise<string> => {
			if (!electronAPI?.getAgentFilesystemMounts) {
				return candidatePath;
			}
			try {
				const mounts = (await electronAPI.getAgentFilesystemMounts(
					searchSpaceId
				)) as AgentFilesystemMount[];
				return normalizeLocalVirtualPathForEditor(candidatePath, mounts);
			} catch {
				return candidatePath;
			}
		},
		[electronAPI, searchSpaceId]
	);

	const isLargeDocument = (editorDoc?.content_size_bytes ?? 0) > LARGE_DOCUMENT_THRESHOLD;

	// `fetchKey` is an explicit re-fetch trigger (escalation bumps it to force
	// a new request even when documentId/searchSpaceId haven't changed).
	useEffect(() => {
		const controller = new AbortController();
		setIsLoading(true);
		setError(null);
		setEditorDoc(null);
		setEditedMarkdown(null);
		setLocalFileContent("");
		setHasCopied(false);
		setIsEditing(false);
		initialLoadDone.current = false;
		changeCountRef.current = 0;
		// Clear any in-flight FindReplacePlugin search before the editor
		// re-mounts on new content (a fresh editor key is generated below
		// from documentId + isEditing, so the previous editor + its
		// decorations are about to be discarded anyway, but we belt-and-
		// brace here for the case where only `fetchKey` changed).
		clearCitationSearch();

		const doFetch = async () => {
			try {
				if (isLocalFileMode) {
					if (!localFilePath) {
						throw new Error("Missing local file path");
					}
					if (!electronAPI?.readAgentLocalFileText) {
						throw new Error("Local file editor is available only in desktop mode.");
					}
					const resolvedLocalPath = await resolveLocalVirtualPath(localFilePath);
					const readResult = await electronAPI.readAgentLocalFileText(
						resolvedLocalPath,
						searchSpaceId
					);
					if (!readResult.ok) {
						throw new Error(readResult.error || "Failed to read local file");
					}
					const inferredTitle = resolvedLocalPath.split("/").pop() || resolvedLocalPath;
					const content: EditorContent = {
						document_id: -1,
						title: inferredTitle,
						document_type: "NOTE",
						source_markdown: readResult.content,
					};
					markdownRef.current = content.source_markdown;
					setLocalFileContent(content.source_markdown);
					setDisplayTitle(title || inferredTitle);
					setEditorDoc(content);
					initialLoadDone.current = true;
					return;
				}
				if (!documentId || !searchSpaceId) {
					throw new Error("Missing document context");
				}
				const token = getBearerToken();
				if (!token) {
					redirectToLogin();
					return;
				}

				const url = new URL(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/editor-content`
				);
				url.searchParams.set("max_length", String(maxLengthOverride ?? LARGE_DOCUMENT_THRESHOLD));
				// `fetchKey` participates here so biome's noUnusedVariables sees it
				// as consumed; bumping it forces a fresh request even when the URL
				// is otherwise identical.
				if (fetchKey > 0) url.searchParams.set("_n", String(fetchKey));

				const response = await authenticatedFetch(url.toString(), { method: "GET" });

				if (controller.signal.aborted) return;

				if (!response.ok) {
					const errorData = await response
						.json()
						.catch(() => ({ detail: "Failed to fetch document" }));
					throw new Error(errorData.detail || "Failed to fetch document");
				}

				const data = await response.json();

				if (data.source_markdown === undefined || data.source_markdown === null) {
					setError(
						"This document does not have editable content. Please re-upload to enable editing."
					);
					setIsLoading(false);
					return;
				}

				markdownRef.current = data.source_markdown;
				setDisplayTitle(data.title || title || "Untitled");
				setEditorDoc(data);
				initialLoadDone.current = true;
			} catch (err) {
				if (controller.signal.aborted) return;
				console.error("Error fetching document:", err);
				setError(err instanceof Error ? err.message : "Failed to fetch document");
			} finally {
				if (!controller.signal.aborted) setIsLoading(false);
			}
		};

		doFetch().catch(() => {});
		return () => controller.abort();
	}, [
		documentId,
		electronAPI,
		isLocalFileMode,
		localFilePath,
		resolveLocalVirtualPath,
		searchSpaceId,
		title,
		fetchKey,
		maxLengthOverride,
		clearCitationSearch,
	]);

	// Reset citation-jump bookkeeping whenever the panel switches to a different
	// document (or local file). Body only writes setters — the deps are the
	// real triggers we want to react to.
	// biome-ignore lint/correctness/useExhaustiveDependencies: documentId/localFilePath are intentional triggers.
	useEffect(() => {
		clearCitationSearch();
		escalatedForRef.current = null;
		lastAppliedChunkIdRef.current = null;
		setHighlightResult(null);
		setMaxLengthOverride(null);
		setFetchKey(0);
		// Drop sticky Plate mode when the panel moves to a different doc
		// — the next doc starts in its preferred render mode (Plate for
		// editable, MarkdownViewer for everything else) until/unless a
		// citation jump targets it.
		setStickyPlateMode(false);
	}, [documentId, localFilePath, clearCitationSearch]);

	// Latch sticky Plate mode the first time a citation jump targets this
	// doc. We keep it sticky for the remainder of this doc session so the
	// highlight effect's `setPendingHighlight(null)` doesn't unmount the
	// editor mid-flight (see comment on `stickyPlateMode` declaration).
	useEffect(() => {
		if (isCitationTarget) setStickyPlateMode(true);
	}, [isCitationTarget]);

	// `isEditorReady` is what `useEffect` actually depends on — `editorRef`
	// is a ref so changes don't trigger re-runs. We flip this to `true` once
	// `PlateEditor` calls back with its live editor instance (its
	// `usePlateEditor` value-init runs synchronously, so by the time this
	// flips true the markdown is already deserialized into the Slate tree).
	const [isEditorReady, setIsEditorReady] = useState(false);
	const handleEditorReady = useCallback((editor: PlateEditorInstance | null) => {
		console.log("[citation:editor] handleEditorReady", { ready: !!editor });
		editorRef.current = editor;
		setIsEditorReady(!!editor);
	}, []);

	// --- Citation jump highlight effect -----------------------------------
	// Drives Plate's FindReplacePlugin to highlight the cited chunk:
	//   1. Build candidate snippets from the chunk text (first sentence,
	//      first 8 words, full chunk if short). Plate's decorate runs per-
	//      block and won't cross block boundaries, so the shorter
	//      candidates exist to give us something that fits in one
	//      paragraph / heading.
	//   2. For each candidate: setOption('search', ...) → redecorate →
	//      wait two animation frames for React to flush → query the editor
	//      DOM for `.${CITATION_HIGHLIGHT_CLASS}`. First hit wins.
	//
	//      Why a className and not a `data-*` attribute? Plate's
	//      `PlateLeaf` runs its props through `useNodeAttributes`, which
	//      only forwards `attributes`, `className`, `ref`, and `style` —
	//      arbitrary `data-*` attributes are silently dropped. `className`
	//      is the only escape hatch guaranteed to survive into the DOM.
	//   3. On hit: smooth-scroll the first match into view, mark the
	//      highlight active (so a click inside the editor can dismiss it),
	//      release the pending atom.
	//   4. On terminal miss: if the doc was truncated and we haven't
	//      escalated yet, bump the fetch's `max_length` to the citation
	//      cap and re-fetch — the post-refetch render will re-run this
	//      effect against the larger preview. Otherwise, release the
	//      atom and show the miss alert.
	useEffect(() => {
		console.log("[citation:effect] fired", {
			isCitationTarget,
			pendingDocId: pending?.documentId,
			pendingChunkId: pending?.chunkId,
			pendingChunkTextLen: pending?.chunkText?.length,
			documentId,
			isLocalFileMode,
			isEditing,
			hasMarkdown: !!editorDoc?.source_markdown,
			markdownLen: editorDoc?.source_markdown?.length,
			truncated: editorDoc?.truncated,
			isEditorReady,
			editorRefSet: !!editorRef.current,
			maxLengthOverride,
		});
		if (!isCitationTarget || !pending) {
			console.log("[citation:effect] guard ✗ no citation target / no pending");
			return;
		}
		if (isLocalFileMode || isEditing) {
			console.log("[citation:effect] guard ✗ localFileMode/editing");
			return;
		}
		if (!editorDoc?.source_markdown) {
			console.log("[citation:effect] guard ✗ source_markdown not ready");
			return;
		}
		if (!isEditorReady) {
			console.log("[citation:effect] guard ✗ editor not ready yet");
			return;
		}
		const editor = editorRef.current;
		if (!editor) {
			console.log("[citation:effect] guard ✗ editorRef.current is null");
			return;
		}

		if (lastAppliedChunkIdRef.current !== pending.chunkId) {
			lastAppliedChunkIdRef.current = pending.chunkId;
		}

		let cancelled = false;

		const finishMiss = () => {
			console.log("[citation:effect] terminal miss — no candidate matched");
			try {
				editor.setOption(FindReplacePlugin, "search", "");
				editor.api.redecorate();
			} catch (err) {
				console.warn("[EditorPanelContent] reset search after miss failed:", err);
			}
			const canEscalate =
				editorDoc.truncated === true &&
				(maxLengthOverride ?? LARGE_DOCUMENT_THRESHOLD) < CITATION_MAX_LENGTH &&
				escalatedForRef.current !== pending.chunkId;
			console.log("[citation:effect] miss decision", {
				truncated: editorDoc.truncated,
				currentMaxLength: maxLengthOverride ?? LARGE_DOCUMENT_THRESHOLD,
				canEscalate,
			});
			if (canEscalate) {
				escalatedForRef.current = pending.chunkId;
				setMaxLengthOverride(CITATION_MAX_LENGTH);
				setFetchKey((k) => k + 1);
				// Keep the atom set so the post-refetch render re-runs.
				return;
			}
			setHighlightResult("miss");
			setPendingHighlight(null);
		};

		const tryCandidates = async () => {
			const candidates = buildCitationSearchCandidates(pending.chunkText);
			console.log("[citation:effect] candidates built", {
				count: candidates.length,
				previews: candidates.map((c) => c.slice(0, 60)),
			});
			if (candidates.length === 0) {
				if (!cancelled) finishMiss();
				return;
			}
			// Resolve the editor's rendered DOM root via Slate's stable
			// `[data-slate-editor="true"]` attribute (set by slate-react's
			// `<Editable>`). Scoping queries to this root prevents
			// `<mark>` elements rendered elsewhere on the page (e.g. chat
			// search-highlight leaves in another mounted PlateEditor) from
			// being mistaken for citation hits.
			const editorRoot = document.querySelector<HTMLElement>('[data-slate-editor="true"]');
			console.log("[citation:effect] editor root", {
				hasRoot: !!editorRoot,
			});
			const root: ParentNode = editorRoot ?? document;

			for (let i = 0; i < candidates.length; i++) {
				const candidate = candidates[i];
				if (cancelled) return;
				try {
					editor.setOption(FindReplacePlugin, "search", candidate);
					editor.api.redecorate();
					console.log(`[citation:effect] try #${i} setOption + redecorate`, {
						len: candidate.length,
						preview: candidate.slice(0, 80),
					});
				} catch (err) {
					console.warn("[EditorPanelContent] setOption/redecorate failed:", err);
					continue;
				}
				// Two rAFs: first lets Slate flush its onChange, second lets
				// React commit the decoration leaves into the DOM.
				await new Promise<void>((resolve) =>
					requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
				);
				if (cancelled) return;
				// Primary probe: by our stable class on the rendered <mark>.
				let el = root.querySelector<HTMLElement>(`.${CITATION_HIGHLIGHT_CLASS}`);
				const classMarkCount = root.querySelectorAll(`.${CITATION_HIGHLIGHT_CLASS}`).length;
				// Diagnostic fallback: any <mark> inside the editor root.
				// If we ever see allMarks > 0 but classMarkCount === 0,
				// the className was stripped again and we need to revisit
				// `useNodeAttributes` filtering.
				const allMarkCount = root.querySelectorAll("mark").length;
				if (!el && allMarkCount > 0) {
					el = root.querySelector<HTMLElement>("mark");
				}
				console.log(`[citation:effect] try #${i} DOM probe`, {
					foundEl: !!el,
					classMarkCount,
					allMarkCount,
					usedFallback: !!el && classMarkCount === 0,
				});
				if (el) {
					try {
						el.scrollIntoView({ block: "center", behavior: "smooth" });
					} catch {
						el.scrollIntoView();
					}
					isHighlightActiveRef.current = true;
					setHighlightResult("exact");
					console.log(`[citation:effect] ✓ exact via candidate #${i} — atom released`);
					// No auto-clear timer — the highlight is intentionally
					// permanent until the user clicks inside the editor (see
					// `handleEditorPointerDown`) or another dismissal trigger
					// fires (doc switch, edit-mode toggle, panel unmount,
					// next citation jump). Sticky Plate mode keeps the
					// editor mounted after the atom clears.
					setPendingHighlight(null);
					return;
				}
			}
			if (!cancelled) finishMiss();
		};

		void tryCandidates();

		return () => {
			cancelled = true;
		};
	}, [
		isCitationTarget,
		pending,
		documentId,
		editorDoc?.source_markdown,
		editorDoc?.truncated,
		isLocalFileMode,
		isEditing,
		isEditorReady,
		maxLengthOverride,
		clearCitationSearch,
		setPendingHighlight,
	]);

	// Cleanup any active highlight on unmount.
	useEffect(() => {
		return () => clearCitationSearch();
	}, [clearCitationSearch]);

	// Toggling into edit mode swaps Plate out of readOnly. Clear the citation
	// search so stale leaves don't linger in the editing surface.
	useEffect(() => {
		if (isEditing) {
			clearCitationSearch();
			setHighlightResult(null);
		}
	}, [isEditing, clearCitationSearch]);

	useEffect(() => {
		return () => {
			if (copyResetTimeoutRef.current) {
				clearTimeout(copyResetTimeoutRef.current);
			}
		};
	}, []);

	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
		if (!initialLoadDone.current) return;
		changeCountRef.current += 1;
		if (changeCountRef.current <= 1) return;
		setEditedMarkdown(md);
	}, []);

	const handleCopy = useCallback(async () => {
		try {
			const textToCopy = markdownRef.current ?? editorDoc?.source_markdown ?? "";
			await navigator.clipboard.writeText(textToCopy);
			setHasCopied(true);
			if (copyResetTimeoutRef.current) {
				clearTimeout(copyResetTimeoutRef.current);
			}
			copyResetTimeoutRef.current = setTimeout(() => {
				setHasCopied(false);
			}, 1400);
		} catch (err) {
			console.error("Error copying content:", err);
		}
	}, [editorDoc?.source_markdown]);

	const handleSave = useCallback(
		async (_options?: { silent?: boolean }) => {
			setSaving(true);
			try {
				if (isLocalFileMode) {
					if (!localFilePath) {
						throw new Error("Missing local file path");
					}
					if (!electronAPI?.writeAgentLocalFileText) {
						throw new Error("Local file editor is available only in desktop mode.");
					}
					const resolvedLocalPath = await resolveLocalVirtualPath(localFilePath);
					const contentToSave = markdownRef.current;
					const writeResult = await electronAPI.writeAgentLocalFileText(
						resolvedLocalPath,
						contentToSave,
						searchSpaceId
					);
					if (!writeResult.ok) {
						throw new Error(writeResult.error || "Failed to save local file");
					}
					setEditorDoc((prev) => (prev ? { ...prev, source_markdown: contentToSave } : prev));
					setEditedMarkdown(markdownRef.current === contentToSave ? null : markdownRef.current);
					return true;
				}
				if (!searchSpaceId || !documentId) {
					throw new Error("Missing document context");
				}
				const token = getBearerToken();
				if (!token) {
					toast.error("Please login to save");
					redirectToLogin();
					return;
				}
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/save`,
					{
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ source_markdown: markdownRef.current }),
					}
				);

				if (!response.ok) {
					const errorData = await response
						.json()
						.catch(() => ({ detail: "Failed to save document" }));
					throw new Error(errorData.detail || "Failed to save document");
				}

				setEditorDoc((prev) => (prev ? { ...prev, source_markdown: markdownRef.current } : prev));
				setEditedMarkdown(null);
				toast.success("Document saved! Reindexing in background...");
				return true;
			} catch (err) {
				console.error("Error saving document:", err);
				toast.error(err instanceof Error ? err.message : "Failed to save document");
				return false;
			} finally {
				setSaving(false);
			}
		},
		[
			documentId,
			electronAPI,
			isLocalFileMode,
			localFilePath,
			resolveLocalVirtualPath,
			searchSpaceId,
		]
	);

	const isEditableType = editorDoc
		? (editorRenderMode === "source_code" ||
				EDITABLE_DOCUMENT_TYPES.has(editorDoc.document_type ?? "")) &&
			!isLargeDocument
		: false;
	// Use PlateEditor for any of:
	//   - Editable doc types (FILE/NOTE) — existing editing UX.
	//   - Active citation jump in flight (`isCitationTarget`) — covers the
	//     mount in the very first render where the atom is set but the
	//     sticky effect hasn't fired yet.
	//   - Sticky Plate mode latched on a previous citation jump — keeps
	//     the editor mounted (with its decorations) after the highlight
	//     effect clears the atom. Resets when the doc changes.
	const renderInPlateEditor = isEditableType || isCitationTarget || stickyPlateMode;
	const hasUnsavedChanges = editedMarkdown !== null;
	const showDesktopHeader = !!onClose;
	const showEditingActions = isEditableType && isEditing;
	const localFileLanguage = inferMonacoLanguageFromPath(localFilePath);

	const handleCancelEditing = useCallback(() => {
		const savedContent = editorDoc?.source_markdown ?? "";
		markdownRef.current = savedContent;
		setLocalFileContent(savedContent);
		setEditedMarkdown(null);
		changeCountRef.current = 0;
		setIsEditing(false);
	}, [editorDoc?.source_markdown]);

	const handleDownloadMarkdown = useCallback(async () => {
		if (!searchSpaceId || !documentId) return;
		setDownloading(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/documents/${documentId}/download-markdown`,
				{ method: "GET" }
			);
			if (!response.ok) throw new Error("Download failed");
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			const disposition = response.headers.get("content-disposition");
			const match = disposition?.match(/filename="(.+)"/);
			a.download = match?.[1] ?? `${editorDoc?.title || "document"}.md`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(url);
			toast.success("Download started");
		} catch {
			toast.error("Failed to download document");
		} finally {
			setDownloading(false);
		}
	}, [documentId, editorDoc?.title, searchSpaceId]);

	// We no longer surface an "approximate" status — Plate's FindReplacePlugin
	// either decorates an exact match or it doesn't, and the candidate snippet
	// strategy (first sentence → first 8 words → full chunk) means we either
	// land on the citation start or fall through to the miss alert.
	const showMissAlert = isCitationTarget && highlightResult === "miss";

	const citationAlerts = showMissAlert && (
		<Alert variant="destructive" className="mb-4">
			<FileQuestionMark className="size-4" />
			<AlertDescription className="flex items-center justify-between gap-4">
				<span>Cited section couldn&apos;t be located in this view.</span>
				{editorDoc?.truncated && (
					<Button
						variant="outline"
						size="sm"
						className="relative shrink-0"
						disabled={downloading}
						onClick={handleDownloadMarkdown}
					>
						<span className={`flex items-center gap-1.5 ${downloading ? "opacity-0" : ""}`}>
							<Download className="size-3.5" />
							Download .md
						</span>
						{downloading && <Spinner size="sm" className="absolute" />}
					</Button>
				)}
			</AlertDescription>
		</Alert>
	);

	const largeDocAlert = isLargeDocument && !isLocalFileMode && editorDoc && (
		<Alert className="mb-4">
			<FileText className="size-4" />
			<AlertDescription className="flex items-center justify-between gap-4">
				<span>
					This document is too large for the editor (
					{Math.round((editorDoc.content_size_bytes ?? 0) / 1024 / 1024)}MB,{" "}
					{editorDoc.chunk_count ?? 0} chunks). Showing a preview below.
				</span>
				<Button
					variant="outline"
					size="sm"
					className="relative shrink-0"
					disabled={downloading}
					onClick={handleDownloadMarkdown}
				>
					<span className={`flex items-center gap-1.5 ${downloading ? "opacity-0" : ""}`}>
						<Download className="size-3.5" />
						Download .md
					</span>
					{downloading && <Spinner size="sm" className="absolute" />}
				</Button>
			</AlertDescription>
		</Alert>
	);

	return (
		<>
			{showDesktopHeader ? (
				<div className="shrink-0 border-b">
					<div className="flex h-14 items-center justify-between px-4">
						<h2 className="text-lg font-medium text-muted-foreground select-none">File</h2>
						<div className="flex items-center gap-1 shrink-0">
							<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
								<XIcon className="size-4" />
								<span className="sr-only">Close editor panel</span>
							</Button>
						</div>
					</div>
					<div className="flex h-10 items-center justify-between gap-2 border-t px-4">
						<div className="min-w-0 flex flex-1 items-center gap-2">
							<p className="truncate text-sm text-muted-foreground">{displayTitle}</p>
						</div>
						<div className="flex items-center gap-1 shrink-0">
							{showEditingActions ? (
								<>
									<Button
										variant="ghost"
										size="sm"
										className="h-6 px-2 text-xs"
										onClick={handleCancelEditing}
										disabled={saving}
									>
										Cancel
									</Button>
									<Button
										variant="secondary"
										size="sm"
										className="relative h-6 w-[56px] px-0 text-xs"
										onClick={async () => {
											const saveSucceeded = await handleSave({ silent: true });
											if (saveSucceeded) setIsEditing(false);
										}}
										disabled={saving || !hasUnsavedChanges}
									>
										<span className={saving ? "opacity-0" : ""}>Save</span>
										{saving && <Spinner size="xs" className="absolute" />}
									</Button>
								</>
							) : (
								<>
									{!isLocalFileMode && editorDoc?.document_type && documentId && (
										<VersionHistoryButton
											documentId={documentId}
											documentType={editorDoc.document_type}
										/>
									)}
									<Button
										variant="ghost"
										size="icon"
										className="size-6"
										onClick={() => {
											void handleCopy();
										}}
										disabled={isLoading || !editorDoc}
									>
										{hasCopied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
										<span className="sr-only">
											{hasCopied ? "Copied file contents" : "Copy file contents"}
										</span>
									</Button>
									{isEditableType && (
										<Button
											variant="ghost"
											size="icon"
											className="size-6"
											onClick={() => {
												changeCountRef.current = 0;
												setEditedMarkdown(null);
												setIsEditing(true);
											}}
										>
											<Pencil className="size-3.5" />
											<span className="sr-only">Edit document</span>
										</Button>
									)}
								</>
							)}
						</div>
					</div>
				</div>
			) : (
				<div className="flex h-14 items-center justify-between border-b px-4 shrink-0">
					<div className="flex flex-1 min-w-0 items-center gap-2">
						<h2 className="text-sm font-semibold truncate">{displayTitle}</h2>
					</div>
					<div className="flex items-center gap-1 shrink-0">
						{showEditingActions ? (
							<>
								<Button
									variant="ghost"
									size="sm"
									className="h-6 px-2 text-xs"
									onClick={handleCancelEditing}
									disabled={saving}
								>
									Cancel
								</Button>
								<Button
									variant="secondary"
									size="sm"
									className="relative h-6 w-[56px] px-0 text-xs"
									onClick={async () => {
										const saveSucceeded = await handleSave({ silent: true });
										if (saveSucceeded) setIsEditing(false);
									}}
									disabled={saving || !hasUnsavedChanges}
								>
									<span className={saving ? "opacity-0" : ""}>Save</span>
									{saving && <Spinner size="xs" className="absolute" />}
								</Button>
							</>
						) : (
							<>
								{!isLocalFileMode && editorDoc?.document_type && documentId && (
									<VersionHistoryButton
										documentId={documentId}
										documentType={editorDoc.document_type}
									/>
								)}
								<Button
									variant="ghost"
									size="icon"
									className="size-6"
									onClick={() => {
										void handleCopy();
									}}
									disabled={isLoading || !editorDoc}
								>
									{hasCopied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
									<span className="sr-only">
										{hasCopied ? "Copied file contents" : "Copy file contents"}
									</span>
								</Button>
								{isEditableType && (
									<Button
										variant="ghost"
										size="icon"
										className="size-6"
										onClick={() => {
											changeCountRef.current = 0;
											setEditedMarkdown(null);
											setIsEditing(true);
										}}
									>
										<Pencil className="size-3.5" />
										<span className="sr-only">Edit document</span>
									</Button>
								)}
							</>
						)}
					</div>
				</div>
			)}

			<div className="flex-1 overflow-hidden">
				{isLoading ? (
					<EditorPanelSkeleton />
				) : error || !editorDoc ? (
					<div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
						{error?.toLowerCase().includes("still being processed") ? (
							<div className="rounded-full bg-muted/50 p-3">
								<RefreshCw className="size-6 text-muted-foreground animate-spin" />
							</div>
						) : (
							<div className="rounded-full bg-muted/50 p-3">
								<FileQuestionMark className="size-6 text-muted-foreground" />
							</div>
						)}
						<div className="space-y-1 max-w-xs">
							<p className="font-medium text-foreground">
								{error?.toLowerCase().includes("still being processed")
									? "Document is processing"
									: "Document unavailable"}
							</p>
							<p className="text-sm text-muted-foreground">
								{error || "An unknown error occurred"}
							</p>
						</div>
					</div>
				) : editorRenderMode === "source_code" ? (
					<div className="h-full overflow-hidden">
						<SourceCodeEditor
							path={localFilePath ?? "local-file.txt"}
							language={localFileLanguage}
							value={localFileContent}
							onSave={() => {
								void handleSave({ silent: true });
							}}
							readOnly={!isEditing}
							onChange={(next) => {
								markdownRef.current = next;
								setLocalFileContent(next);
								if (!initialLoadDone.current) return;
								setEditedMarkdown(next === (editorDoc?.source_markdown ?? "") ? null : next);
							}}
						/>
					</div>
				) : isLargeDocument && !isLocalFileMode && !isCitationTarget ? (
					// Large doc, no active citation — fast Streamdown preview
					// + download CTA. We only fall back to MarkdownViewer here
					// because Plate is heavy on multi-MB docs and the user
					// isn't waiting on a specific citation to render.
					<div className="h-full overflow-y-auto px-5 py-4">
						{largeDocAlert}
						<MarkdownViewer content={editorDoc.source_markdown} />
					</div>
				) : renderInPlateEditor ? (
					// Editable doc (FILE/NOTE) OR active citation jump (any
					// doc type). The citation path uses Plate's
					// FindReplacePlugin for native, decoration-based
					// highlighting — see the citation-jump highlight effect
					// above for how `editorRef` and `handleEditorReady` are
					// wired.
					<div className="flex h-full min-h-0 flex-col">
						{(citationAlerts || (isLargeDocument && isCitationTarget && !isLocalFileMode)) && (
							<div className="shrink-0 px-5 pt-4">
								{isLargeDocument && isCitationTarget && largeDocAlert}
								{citationAlerts}
							</div>
						)}
						<div className="flex-1 min-h-0 overflow-hidden" onPointerDown={handleEditorPointerDown}>
							<PlateEditor
								key={`${isLocalFileMode ? (localFilePath ?? "local-file") : documentId}-${isEditing ? "editing" : "viewing"}`}
								preset="full"
								markdown={editorDoc.source_markdown}
								onMarkdownChange={handleMarkdownChange}
								readOnly={!isEditing}
								placeholder="Start writing..."
								editorVariant="default"
								allowModeToggle={false}
								reserveToolbarSpace
								defaultEditing={isEditing}
								className="[&_[role=toolbar]]:!bg-sidebar"
								onEditorReady={handleEditorReady}
							/>
						</div>
					</div>
				) : (
					<div className="h-full overflow-y-auto px-5 py-4">
						<MarkdownViewer content={editorDoc.source_markdown} />
					</div>
				)}
			</div>
		</>
	);
}

function DesktopEditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const closePanel = useSetAtom(closeEditorPanelAtom);

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") closePanel();
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [closePanel]);

	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;
	if (!panelState.isOpen || !hasTarget) return null;

	return (
		<div className="flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l bg-sidebar text-sidebar-foreground animate-in slide-in-from-right-4 duration-300 ease-out">
			<EditorPanelContent
				kind={panelState.kind}
				documentId={panelState.documentId ?? undefined}
				localFilePath={panelState.localFilePath ?? undefined}
				searchSpaceId={panelState.searchSpaceId ?? undefined}
				title={panelState.title}
				onClose={closePanel}
			/>
		</div>
	);
}

function MobileEditorDrawer() {
	const panelState = useAtomValue(editorPanelAtom);
	const closePanel = useSetAtom(closeEditorPanelAtom);

	if (panelState.kind === "local_file") return null;

	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;
	if (!hasTarget) return null;

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[90vh] max-h-[90vh] z-80 bg-sidebar overflow-hidden"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">{panelState.title || "Editor"}</DrawerTitle>
				<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
					<EditorPanelContent
						kind={panelState.kind}
						documentId={panelState.documentId ?? undefined}
						localFilePath={panelState.localFilePath ?? undefined}
						searchSpaceId={panelState.searchSpaceId ?? undefined}
						title={panelState.title}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

export function EditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;

	if (!panelState.isOpen || !hasTarget) return null;
	if (!isDesktop && panelState.kind === "local_file") return null;

	if (isDesktop) {
		return <DesktopEditorPanel />;
	}

	return <MobileEditorDrawer />;
}

export function MobileEditorPanel() {
	const panelState = useAtomValue(editorPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const hasTarget =
		panelState.kind === "document"
			? !!panelState.documentId && !!panelState.searchSpaceId
			: !!panelState.localFilePath;

	if (isDesktop || !panelState.isOpen || !hasTarget || panelState.kind === "local_file")
		return null;

	return <MobileEditorDrawer />;
}
