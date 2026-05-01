"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import {
	MarkdownTextPrimitive,
	unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
	useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown";
import { useSetAtom } from "jotai";
import { ExternalLinkIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useTheme } from "next-themes";
import { createContext, memo, type ReactNode, useCallback, useContext, useRef } from "react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { openEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { ImagePreview, ImageRoot, ImageZoom } from "@/components/assistant-ui/image";
import "katex/dist/katex.min.css";
import { processChildrenWithCitations } from "@/components/citations/citation-renderer";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { useElectronAPI } from "@/hooks/use-platform";
import { type CitationUrlMap, preprocessCitationMarkdown } from "@/lib/citations/citation-parser";
import { cn } from "@/lib/utils";

function MarkdownCodeBlockSkeleton() {
	return (
		<div
			className="mt-4 overflow-hidden rounded-2xl border"
			style={{ background: "var(--syntax-bg)" }}
		>
			<div className="flex items-center justify-between gap-4 border-b px-4 py-2">
				<Skeleton className="h-3 w-16" />
				<Skeleton className="h-8 w-8 rounded-md" />
			</div>
			<div className="space-y-2 p-4">
				<Skeleton className="h-4 w-11/12" />
				<Skeleton className="h-4 w-10/12" />
				<Skeleton className="h-4 w-8/12" />
				<Skeleton className="h-4 w-9/12" />
			</div>
		</div>
	);
}

const LazyMarkdownCodeBlock = dynamic(
	() => import("./markdown-code-block").then((mod) => mod.MarkdownCodeBlock),
	{
		loading: () => <MarkdownCodeBlockSkeleton />,
	}
);

// Per-render URL placeholder map propagated to component overrides via
// React Context. Replaces the previous module-level `_pendingUrlCitations`
// state, which was unsafe under concurrent renders / SSR.
type CitationUrlMapRef = { current: CitationUrlMap };
const EMPTY_URL_MAP: CitationUrlMap = new Map();
const CitationUrlMapContext = createContext<CitationUrlMapRef>({ current: EMPTY_URL_MAP });

function useCitationUrlMap(): CitationUrlMap {
	return useContext(CitationUrlMapContext).current;
}

/**
 * Preprocess raw markdown before it reaches the remark/rehype pipeline.
 * - Replaces URL-based citations with safe placeholders (prevents GFM autolinks)
 * - Normalises LaTeX delimiters to dollar-sign syntax for remark-math
 */
function preprocessMarkdown(content: string, urlMapRef: CitationUrlMapRef): string {
	// Replace URL-based citations with safe placeholders BEFORE markdown parsing.
	// GFM autolinks would otherwise convert the https://... inside [citation:URL]
	// into an <a> element, splitting the text and preventing our citation regex
	// from matching the full pattern.
	const { content: rewritten, urlMap } = preprocessCitationMarkdown(content);
	urlMapRef.current = urlMap;
	content = rewritten;

	// All math forms are normalised to $$...$$ so we can disable single-dollar
	// inline math in remark-math (otherwise currency like "$3,120.00 and $0.00"
	// gets parsed as a LaTeX expression).
	// 1. Block math: \[...\] → $$...$$
	content = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
	// 2. Inline math: \(...\) → $$...$$
	content = content.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$$${inner}$$`);
	// 3. Block: \begin{equation}...\end{equation} → $$...$$
	content = content.replace(
		/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
		(_, inner) => `$$${inner}$$`
	);
	// 4. Block: \begin{displaymath}...\end{displaymath} → $$...$$
	content = content.replace(
		/\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}/g,
		(_, inner) => `$$${inner}$$`
	);
	// 5. Inline: \begin{math}...\end{math} → $$...$$
	content = content.replace(
		/\\begin\{math\}([\s\S]*?)\\end\{math\}/g,
		(_, inner) => `$$${inner}$$`
	);
	// 6. Strip backtick wrapping around math: `$$...$$` → $$...$$ and `$...$` → $...$
	content = content.replace(/`(\${1,2})((?:(?!\1).)+)\1`/g, "$1$2$1");

	// Ensure markdown headings (## ...) always start on their own line.
	content = content.replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");

	return content;
}

const MarkdownTextImpl = () => {
	const urlMapRef = useRef<CitationUrlMap>(EMPTY_URL_MAP);
	const preprocess = useCallback((content: string) => preprocessMarkdown(content, urlMapRef), []);
	return (
		<CitationUrlMapContext.Provider value={urlMapRef}>
			<MarkdownTextPrimitive
				smooth={false}
				remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: false }]]}
				rehypePlugins={[rehypeKatex]}
				className="aui-md"
				components={defaultComponents}
				preprocess={preprocess}
			/>
		</CitationUrlMapContext.Provider>
	);
};

export const MarkdownText = memo(MarkdownTextImpl);

function extractDomain(url: string): string {
	try {
		const parsed = new URL(url);
		return parsed.hostname.replace(/^www\./, "");
	} catch {
		return "";
	}
}

// Canonical local-file virtual paths are mount-prefixed: /<mount>/<relative/path>
const LOCAL_FILE_PATH_REGEX = /^\/[a-z0-9_-]+\/[^\s`]+(?:\/[^\s`]+)*$/;

type AgentFilesystemMount = {
	mount: string;
	rootPath: string;
};

function normalizeLocalVirtualPathForEditor(
	candidatePath: string,
	mounts: AgentFilesystemMount[]
): string {
	const normalizedCandidate = candidatePath.trim().replace(/\\/g, "/").replace(/\/+/g, "/");
	if (!normalizedCandidate) {
		return candidatePath;
	}
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

function isVirtualFilePathToken(value: string): boolean {
	if (!LOCAL_FILE_PATH_REGEX.test(value) || value.startsWith("//")) {
		return false;
	}
	const normalized = value.replace(/\/+$/, "");
	const segments = normalized.split("/").filter(Boolean);
	return segments.length >= 2;
}

function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
	if (!src) return null;

	const domain = extractDomain(src);

	return (
		<div className="my-4 w-fit max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none">
			<ImageRoot variant="ghost" size="full">
				<ImageZoom src={src} alt={alt || "Image"}>
					<ImagePreview
						src={src}
						alt={alt || "Image"}
						className="max-h-[20rem] w-auto max-w-full object-contain"
					/>
				</ImageZoom>
			</ImageRoot>

			<div className="flex items-center justify-between px-5 py-3">
				<div className="min-w-0 flex-1">
					{alt && alt !== "Image" && (
						<p className="text-sm font-semibold text-foreground line-clamp-2">{alt}</p>
					)}
					{domain && <p className="text-xs text-muted-foreground mt-0.5 truncate">{domain}</p>}
				</div>
				<a
					href={src}
					target="_blank"
					rel="noopener noreferrer"
					className="ml-3 shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
					onClick={(e) => e.stopPropagation()}
				>
					Open
					<ExternalLinkIcon className="size-3" />
				</a>
			</div>
		</div>
	);
}

const defaultComponents = memoizeMarkdownComponents({
	h1: function H1({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h1
				className={cn(
					"aui-md-h1 mb-8 scroll-m-20 font-extrabold text-4xl tracking-tight last:mb-0",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</h1>
		);
	},
	h2: function H2({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h2
				className={cn(
					"aui-md-h2 mt-8 mb-4 scroll-m-20 font-semibold text-3xl tracking-tight first:mt-0 last:mb-0",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</h2>
		);
	},
	h3: function H3({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h3
				className={cn(
					"aui-md-h3 mt-6 mb-4 scroll-m-20 font-semibold text-2xl tracking-tight first:mt-0 last:mb-0",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</h3>
		);
	},
	h4: function H4({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h4
				className={cn(
					"aui-md-h4 mt-6 mb-4 scroll-m-20 font-semibold text-xl tracking-tight first:mt-0 last:mb-0",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</h4>
		);
	},
	h5: function H5({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h5
				className={cn("aui-md-h5 my-4 font-semibold text-lg first:mt-0 last:mb-0", className)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</h5>
		);
	},
	h6: function H6({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<h6 className={cn("aui-md-h6 my-4 font-semibold first:mt-0 last:mb-0", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</h6>
		);
	},
	p: function P({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<p className={cn("aui-md-p mt-5 mb-5 leading-7 first:mt-0 last:mb-0", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</p>
		);
	},
	a: function A({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<a
				className={cn("aui-md-a font-medium text-primary underline underline-offset-4", className)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</a>
		);
	},
	blockquote: function Blockquote({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<blockquote className={cn("aui-md-blockquote border-l-2 pl-6 italic", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</blockquote>
		);
	},
	ul: ({ className, ...props }) => (
		<ul className={cn("aui-md-ul my-5 ml-6 list-disc [&>li]:mt-2", className)} {...props} />
	),
	ol: ({ className, ...props }) => (
		<ol className={cn("aui-md-ol my-5 ml-6 list-decimal [&>li]:mt-2", className)} {...props} />
	),
	li: function Li({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<li className={cn("aui-md-li", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</li>
		);
	},
	hr: ({ className, ...props }) => (
		<hr className={cn("aui-md-hr my-5 border-b", className)} {...props} />
	),
	table: ({ className, ...props }) => (
		<div className="aui-md-table-wrapper my-5 overflow-hidden rounded-2xl border">
			<Table className={cn("aui-md-table", className)} {...props} />
		</div>
	),
	thead: ({ className, ...props }) => (
		<TableHeader className={cn("aui-md-thead", className)} {...props} />
	),
	tbody: ({ className, ...props }) => (
		<TableBody className={cn("aui-md-tbody", className)} {...props} />
	),
	th: function Th({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<TableHead
				className={cn(
					"aui-md-th bg-muted/50 whitespace-normal [[align=center]]:text-center [[align=right]]:text-right",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</TableHead>
		);
	},
	td: function Td({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<TableCell
				className={cn(
					"aui-md-td whitespace-normal [[align=center]]:text-center [[align=right]]:text-right",
					className
				)}
				{...props}
			>
				{processChildrenWithCitations(children, urlMap)}
			</TableCell>
		);
	},
	tr: ({ className, ...props }) => <TableRow className={cn("aui-md-tr", className)} {...props} />,
	sup: ({ className, ...props }) => (
		<sup className={cn("aui-md-sup [&>a]:text-xs [&>a]:no-underline", className)} {...props} />
	),
	pre: ({ children }) => <>{children}</>,
	code: function Code({ className, children, ...props }) {
		const isCodeBlock = useIsMarkdownCodeBlock();
		const { resolvedTheme } = useTheme();
		const openEditorPanel = useSetAtom(openEditorPanelAtom);
		const params = useParams();
		const electronAPI = useElectronAPI();
		const language = /language-(\w+)/.exec(className || "")?.[1] ?? "text";
		const codeString = String(children).replace(/\n$/, "");
		const isWebLocalFileCodeBlock =
			isCodeBlock &&
			!electronAPI &&
			isVirtualFilePathToken(codeString.trim()) &&
			!codeString.trim().startsWith("//") &&
			!codeString.includes("\n");
		if (!isCodeBlock) {
			const inlineValue = String(children ?? "").trim();
			const normalizedInlinePath = inlineValue.replace(/\/+$/, "");
			const leafSegment = normalizedInlinePath.split("/").filter(Boolean).at(-1) ?? "";
			const isLikelyFolder =
				inlineValue.endsWith("/") || !leafSegment || !leafSegment.includes(".");
			const isLocalPath =
				!!electronAPI &&
				isVirtualFilePathToken(inlineValue) &&
				!inlineValue.startsWith("//") &&
				!isLikelyFolder;
			const displayLocalPath = inlineValue.replace(/^\/+/, "");
			const searchSpaceIdParam = params?.search_space_id;
			const parsedSearchSpaceId = Array.isArray(searchSpaceIdParam)
				? Number(searchSpaceIdParam[0])
				: Number(searchSpaceIdParam);
			if (isLocalPath) {
				return (
					<button
						type="button"
						className={cn(
							"cursor-pointer font-mono text-[0.9em] font-medium text-primary underline underline-offset-4 transition-colors hover:text-primary/80"
						)}
						onClick={(event) => {
							event.preventDefault();
							event.stopPropagation();
							void (async () => {
								let resolvedLocalPath = inlineValue;
								const resolvedSearchSpaceId = Number.isFinite(parsedSearchSpaceId)
									? parsedSearchSpaceId
									: undefined;
								if (electronAPI?.getAgentFilesystemMounts) {
									try {
										const mounts = (await electronAPI.getAgentFilesystemMounts(
											resolvedSearchSpaceId
										)) as AgentFilesystemMount[];
										resolvedLocalPath = normalizeLocalVirtualPathForEditor(inlineValue, mounts);
									} catch {
										// Fall back to the raw inline path if mount lookup fails.
									}
								}
								openEditorPanel({
									kind: "local_file",
									localFilePath: resolvedLocalPath,
									title: resolvedLocalPath.split("/").pop() || resolvedLocalPath,
									searchSpaceId: resolvedSearchSpaceId,
								});
							})();
						}}
						title="Open in editor panel"
					>
						{displayLocalPath}
					</button>
				);
			}
			return (
				<code
					className={cn(
						"aui-md-inline-code rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[0.9em] font-normal",
						className
					)}
					{...props}
				>
					{children}
				</code>
			);
		}
		if (isWebLocalFileCodeBlock) {
			return (
				<code
					className={cn(
						"aui-md-inline-code rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[0.9em] font-normal",
						className
					)}
					{...props}
				>
					{codeString.trim()}
				</code>
			);
		}
		return (
			<LazyMarkdownCodeBlock
				className={className}
				language={language}
				codeText={codeString}
				isDarkMode={resolvedTheme === "dark"}
			/>
		);
	},
	strong: function Strong({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<strong className={cn("aui-md-strong font-semibold", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</strong>
		);
	},
	em: function Em({ className, children, ...props }) {
		const urlMap = useCitationUrlMap();
		return (
			<em className={cn("aui-md-em", className)} {...props}>
				{processChildrenWithCitations(children, urlMap)}
			</em>
		);
	},
	img: ({ src, alt }) => (
		<MarkdownImage src={typeof src === "string" ? src : undefined} alt={alt} />
	),
	CodeHeader: () => null,
});
