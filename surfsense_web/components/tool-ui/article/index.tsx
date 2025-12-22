"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
	AlertCircleIcon,
	BookOpenIcon,
	CalendarIcon,
	ExternalLinkIcon,
	FileTextIcon,
	UserIcon,
} from "lucide-react";
import { Component, type ReactNode, useCallback } from "react";

/**
 * Article component props
 */
export interface ArticleProps {
	/** Unique identifier for the article */
	id: string;
	/** Asset identifier (usually the URL) */
	assetId?: string;
	/** Article title */
	title: string;
	/** Brief description or excerpt */
	description?: string;
	/** Full content of the article (markdown) */
	content?: string;
	/** URL to the original article */
	href?: string;
	/** Domain of the article source */
	domain?: string;
	/** Author name */
	author?: string;
	/** Publication date */
	date?: string;
	/** Word count */
	wordCount?: number;
	/** Whether content was truncated */
	wasTruncated?: boolean;
	/** Optional max width */
	maxWidth?: string;
	/** Optional error message */
	error?: string;
	/** Optional className */
	className?: string;
	/** Response actions */
	responseActions?: Array<{
		id: string;
		label: string;
		variant?: "default" | "outline";
	}>;
	/** Response action handler */
	onResponseAction?: (actionId: string) => void;
}

/**
 * Serializable article data type (from backend)
 */
export interface SerializableArticle {
	id: string;
	assetId?: string;
	kind?: "article";
	title: string;
	description?: string;
	content?: string;
	href?: string;
	domain?: string;
	author?: string;
	date?: string;
	word_count?: number;
	wordCount?: number;
	was_truncated?: boolean;
	wasTruncated?: boolean;
	error?: string;
}

/**
 * Parse serializable article data to ArticleProps
 */
export function parseSerializableArticle(data: unknown): ArticleProps {
	const obj = data as Record<string, unknown>;
	return {
		id: String(obj.id || "article-unknown"),
		assetId: obj.assetId as string | undefined,
		title: String(obj.title || "Untitled Article"),
		description: obj.description as string | undefined,
		content: obj.content as string | undefined,
		href: obj.href as string | undefined,
		domain: obj.domain as string | undefined,
		author: obj.author as string | undefined,
		date: obj.date as string | undefined,
		wordCount: (obj.word_count || obj.wordCount) as number | undefined,
		wasTruncated: (obj.was_truncated || obj.wasTruncated) as boolean | undefined,
		error: obj.error as string | undefined,
	};
}

/**
 * Format word count for display
 */
function formatWordCount(count: number): string {
	if (count >= 1000) {
		return `${(count / 1000).toFixed(1)}k words`;
	}
	return `${count} words`;
}

/**
 * Article card component for displaying scraped webpage content
 */
export function Article({
	id,
	title,
	description,
	content,
	href,
	domain,
	author,
	date,
	wordCount,
	wasTruncated,
	maxWidth = "100%",
	error,
	className,
	responseActions,
	onResponseAction,
}: ArticleProps) {
	const handleCardClick = useCallback(() => {
		if (href) {
			window.open(href, "_blank", "noopener,noreferrer");
		}
	}, [href]);

	// Error state
	if (error) {
		return (
			<Card
				id={id}
				className={cn(
					"overflow-hidden border-destructive/20 bg-destructive/5",
					className
				)}
				style={{ maxWidth }}
			>
				<CardContent className="p-4">
					<div className="flex items-center gap-3">
						<div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
							<AlertCircleIcon className="size-5 text-destructive" />
						</div>
						<div className="flex-1 min-w-0">
							<p className="font-medium text-destructive text-sm">
								Failed to scrape webpage
							</p>
							{href && (
								<p className="text-muted-foreground text-xs mt-0.5 truncate">
									{href}
								</p>
							)}
							<p className="text-muted-foreground text-xs mt-1">{error}</p>
						</div>
					</div>
				</CardContent>
			</Card>
		);
	}

	return (
		<TooltipProvider>
			<Card
				id={id}
				className={cn(
					"group relative overflow-hidden transition-all duration-200",
					"hover:shadow-lg hover:border-primary/20",
					href && "cursor-pointer",
					className
				)}
				style={{ maxWidth }}
				onClick={href ? handleCardClick : undefined}
				role={href ? "link" : undefined}
				tabIndex={href ? 0 : undefined}
				onKeyDown={(e) => {
					if (href && (e.key === "Enter" || e.key === " ")) {
						e.preventDefault();
						handleCardClick();
					}
				}}
			>
				{/* Header */}
				<CardContent className="p-4">
					<div className="flex items-start gap-3">
						{/* Icon */}
						<div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
							<BookOpenIcon className="size-5 text-primary" />
						</div>

						{/* Content */}
						<div className="flex-1 min-w-0">
							{/* Title */}
							<h3 className="font-semibold text-sm line-clamp-2 group-hover:text-primary transition-colors">
								{title}
							</h3>

							{/* Description */}
							{description && (
								<p className="text-muted-foreground text-xs mt-1 line-clamp-2">
									{description}
								</p>
							)}

							{/* Metadata row */}
							<div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-muted-foreground">
								{domain && (
									<Tooltip>
										<TooltipTrigger asChild>
											<span className="flex items-center gap-1">
												<ExternalLinkIcon className="size-3" />
												<span className="truncate max-w-[120px]">{domain}</span>
											</span>
										</TooltipTrigger>
										<TooltipContent>
											<p>Source: {domain}</p>
										</TooltipContent>
									</Tooltip>
								)}

								{author && (
									<Tooltip>
										<TooltipTrigger asChild>
											<span className="flex items-center gap-1">
												<UserIcon className="size-3" />
												<span className="truncate max-w-[100px]">{author}</span>
											</span>
										</TooltipTrigger>
										<TooltipContent>
											<p>Author: {author}</p>
										</TooltipContent>
									</Tooltip>
								)}

								{date && (
									<span className="flex items-center gap-1">
										<CalendarIcon className="size-3" />
										<span>{date}</span>
									</span>
								)}

								{wordCount && (
									<Tooltip>
										<TooltipTrigger asChild>
											<span className="flex items-center gap-1">
												<FileTextIcon className="size-3" />
												<span>{formatWordCount(wordCount)}</span>
												{wasTruncated && (
													<span className="text-warning">(truncated)</span>
												)}
											</span>
										</TooltipTrigger>
										<TooltipContent>
											<p>
												{wasTruncated
													? "Content was truncated due to length"
													: "Full article content available"}
											</p>
										</TooltipContent>
									</Tooltip>
								)}
							</div>
						</div>

						{/* External link indicator */}
						{href && (
							<div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
								<ExternalLinkIcon className="size-4 text-muted-foreground" />
							</div>
						)}
					</div>

					{/* Response actions */}
					{responseActions && responseActions.length > 0 && (
						<div className="flex gap-2 mt-3 pt-3 border-t">
							{responseActions.map((action) => (
								<button
									key={action.id}
									type="button"
									onClick={(e) => {
										e.stopPropagation();
										onResponseAction?.(action.id);
									}}
									className={cn(
										"px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
										action.variant === "outline"
											? "border border-input bg-background hover:bg-accent hover:text-accent-foreground"
											: "bg-primary text-primary-foreground hover:bg-primary/90"
									)}
								>
									{action.label}
								</button>
							))}
						</div>
					)}
				</CardContent>
			</Card>
		</TooltipProvider>
	);
}

/**
 * Loading state for article component
 */
export function ArticleLoading({
	title = "Loading article...",
}: { title?: string }) {
	return (
		<Card className="overflow-hidden animate-pulse">
			<CardContent className="p-4">
				<div className="flex items-start gap-3">
					<div className="size-10 rounded-lg bg-muted" />
					<div className="flex-1 space-y-2">
						<div className="h-4 bg-muted rounded w-3/4" />
						<div className="h-3 bg-muted rounded w-full" />
						<div className="h-3 bg-muted rounded w-1/2" />
					</div>
				</div>
				<p className="text-xs text-muted-foreground mt-3">{title}</p>
			</CardContent>
		</Card>
	);
}

/**
 * Skeleton for article component
 */
export function ArticleSkeleton() {
	return (
		<Card className="overflow-hidden">
			<CardContent className="p-4">
				<div className="flex items-start gap-3 animate-pulse">
					<div className="size-10 rounded-lg bg-muted" />
					<div className="flex-1 space-y-2">
						<div className="h-4 bg-muted rounded w-3/4" />
						<div className="h-3 bg-muted rounded w-full" />
						<div className="h-3 bg-muted rounded w-2/3" />
					</div>
				</div>
			</CardContent>
		</Card>
	);
}

/**
 * Error boundary props
 */
interface ErrorBoundaryProps {
	children: ReactNode;
	fallback?: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
}

/**
 * Error boundary for article component
 */
export class ArticleErrorBoundary extends Component<
	ErrorBoundaryProps,
	ErrorBoundaryState
> {
	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(): ErrorBoundaryState {
		return { hasError: true };
	}

	render() {
		if (this.state.hasError) {
			return (
				this.props.fallback || (
					<Card className="overflow-hidden border-destructive/20 bg-destructive/5">
						<CardContent className="p-4">
							<div className="flex items-center gap-3">
								<AlertCircleIcon className="size-5 text-destructive" />
								<p className="text-sm text-destructive">
									Failed to render article
								</p>
							</div>
						</CardContent>
					</Card>
				)
			);
		}

		return this.props.children;
	}
}

