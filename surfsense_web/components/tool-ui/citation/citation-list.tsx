"use client";

import type { LucideIcon } from "lucide-react";
import { Code2, Database, ExternalLink, File, FileText, Globe, Newspaper } from "lucide-react";
import * as React from "react";
import { openSafeNavigationHref, resolveSafeNavigationHref } from "../shared/media";
import { cn, Popover, PopoverContent, PopoverTrigger } from "./_adapter";
import { Citation } from "./citation";
import type { CitationType, CitationVariant, SerializableCitation } from "./schema";
import NextImage from 'next/image';


const TYPE_ICONS: Record<CitationType, LucideIcon> = {
	webpage: Globe,
	document: FileText,
	article: Newspaper,
	api: Database,
	code: Code2,
	other: File,
};

function useHoverPopover(delay = 100) {
	const [open, setOpen] = React.useState(false);
	const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
	const containerRef = React.useRef<HTMLDivElement>(null);

	const handleMouseEnter = React.useCallback(() => {
		if (timeoutRef.current) clearTimeout(timeoutRef.current);
		timeoutRef.current = setTimeout(() => setOpen(true), delay);
	}, [delay]);

	const handleMouseLeave = React.useCallback(() => {
		if (timeoutRef.current) clearTimeout(timeoutRef.current);
		timeoutRef.current = setTimeout(() => setOpen(false), delay);
	}, [delay]);

	const handleFocus = React.useCallback(() => {
		if (timeoutRef.current) clearTimeout(timeoutRef.current);
		setOpen(true);
	}, []);

	const handleBlur = React.useCallback(
		(e: React.FocusEvent) => {
			const relatedTarget = e.relatedTarget as HTMLElement | null;
			if (containerRef.current?.contains(relatedTarget)) {
				return;
			}
			if (relatedTarget?.closest("[data-radix-popper-content-wrapper]")) {
				return;
			}
			if (timeoutRef.current) clearTimeout(timeoutRef.current);
			timeoutRef.current = setTimeout(() => setOpen(false), delay);
		},
		[delay]
	);

	React.useEffect(() => {
		return () => {
			if (timeoutRef.current) clearTimeout(timeoutRef.current);
		};
	}, []);

	return {
		open,
		setOpen,
		containerRef,
		handleMouseEnter,
		handleMouseLeave,
		handleFocus,
		handleBlur,
	};
}

export interface CitationListProps {
	id: string;
	citations: SerializableCitation[];
	variant?: CitationVariant;
	maxVisible?: number;
	className?: string;
	onNavigate?: (href: string, citation: SerializableCitation) => void;
}

export function CitationList(props: CitationListProps) {
	const { id, citations, variant = "default", maxVisible, className, onNavigate } = props;

	const shouldTruncate = maxVisible !== undefined && citations.length > maxVisible;
	const visibleCitations = shouldTruncate ? citations.slice(0, maxVisible) : citations;
	const overflowCitations = shouldTruncate ? citations.slice(maxVisible) : [];
	const overflowCount = overflowCitations.length;

	const wrapperClass =
		variant === "inline" ? "flex flex-wrap items-center gap-1.5" : "flex flex-col gap-2";

	// Stacked variant: overlapping favicons with popover
	if (variant === "stacked") {
		return (
			<StackedCitations
				id={id}
				citations={citations}
				className={className}
				onNavigate={onNavigate}
			/>
		);
	}

	if (variant === "default") {
		return (
			<div
				className={cn("isolate flex flex-col gap-4", className)}
				data-tool-ui-id={id}
				data-slot="citation-list"
			>
				{visibleCitations.map((citation) => (
					<Citation key={citation.id} {...citation} variant="default" onNavigate={onNavigate} />
				))}
				{shouldTruncate && (
					<OverflowIndicator
						citations={overflowCitations}
						count={overflowCount}
						variant="default"
						onNavigate={onNavigate}
					/>
				)}
			</div>
		);
	}

	return (
		<div
			className={cn("isolate", wrapperClass, className)}
			data-tool-ui-id={id}
			data-slot="citation-list"
		>
			{visibleCitations.map((citation) => (
				<Citation key={citation.id} {...citation} variant={variant} onNavigate={onNavigate} />
			))}
			{shouldTruncate && (
				<OverflowIndicator
					citations={overflowCitations}
					count={overflowCount}
					variant={variant}
					onNavigate={onNavigate}
				/>
			)}
		</div>
	);
}

interface OverflowIndicatorProps {
	citations: SerializableCitation[];
	count: number;
	variant: CitationVariant;
	onNavigate?: (href: string, citation: SerializableCitation) => void;
}

function OverflowIndicator({ citations, count, variant, onNavigate }: OverflowIndicatorProps) {
	const { open, handleMouseEnter, handleMouseLeave } = useHoverPopover();

	const handleClick = (citation: SerializableCitation) => {
		const href = resolveSafeNavigationHref(citation.href);
		if (!href) return;
		if (onNavigate) {
			onNavigate(href, citation);
		} else {
			openSafeNavigationHref(href);
		}
	};

	const popoverContent = (
		<div className="flex max-h-72 flex-col overflow-y-auto">
			{citations.map((citation) => (
				<OverflowItem key={citation.id} citation={citation} onClick={() => handleClick(citation)} />
			))}
		</div>
	);

	if (variant === "inline") {
		return (
			<Popover open={open}>
				<PopoverTrigger asChild>
					<button
						type="button"
						onMouseEnter={handleMouseEnter}
						onMouseLeave={handleMouseLeave}
						className={cn(
							"inline-flex items-center gap-1 rounded-md px-2 py-1",
							"bg-muted/60 text-sm tabular-nums",
							"transition-colors duration-150",
							"hover:bg-muted",
							"focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none"
						)}
					>
						<span className="text-muted-foreground">+{count} more</span>
					</button>
				</PopoverTrigger>
				<PopoverContent
					side="top"
					align="start"
					className="w-80 p-1"
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
					onOpenAutoFocus={(e) => e.preventDefault()}
				>
					{popoverContent}
				</PopoverContent>
			</Popover>
		);
	}

	// Default variant
	return (
		<Popover open={open}>
			<PopoverTrigger asChild>
				<button
					type="button"
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
					className={cn(
						"flex items-center justify-center rounded-xl px-4 py-3",
						"border-border bg-card border border-dashed",
						"transition-colors duration-150",
						"hover:border-foreground/25 hover:bg-muted/50",
						"focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
					)}
				>
					<span className="text-muted-foreground text-sm tabular-nums">+{count} more sources</span>
				</button>
			</PopoverTrigger>
			<PopoverContent
				side="bottom"
				align="start"
				className="w-80 p-1"
				onMouseEnter={handleMouseEnter}
				onMouseLeave={handleMouseLeave}
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
				{popoverContent}
			</PopoverContent>
		</Popover>
	);
}

interface OverflowItemProps {
	citation: SerializableCitation;
	onClick: () => void;
}

function OverflowItem({ citation, onClick }: OverflowItemProps) {
	const TypeIcon = TYPE_ICONS[citation.type ?? "webpage"] ?? Globe;

	return (
		<button
			type="button"
			onClick={onClick}
			className="group hover:bg-muted focus-visible:bg-muted flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-left transition-colors focus-visible:outline-none"
		>
			{citation.favicon ? (
				<NextImage
					src={citation.favicon}
					alt=""
					aria-hidden="true"
					width={18}
					height={18}
					className="size-4.5 rounded-full object-cover"
					unoptimized={true}
				/>
				) : (
				<TypeIcon className="text-muted-foreground size-3" aria-hidden="true" />
				)}
			<div className="min-w-0 flex-1">
				<p className="group-hover:decoration-foreground/30 truncate text-sm font-medium group-hover:underline group-hover:underline-offset-2">
					{citation.title}
				</p>
				<p className="text-muted-foreground truncate text-xs">{citation.domain}</p>
			</div>
			<ExternalLink className="text-muted-foreground mt-0.5 size-3.5 shrink-0 self-start opacity-0 transition-opacity group-hover:opacity-100" />
		</button>
	);
}

interface StackedCitationsProps {
	id: string;
	citations: SerializableCitation[];
	className?: string;
	onNavigate?: (href: string, citation: SerializableCitation) => void;
}

function StackedCitations({ id, citations, className, onNavigate }: StackedCitationsProps) {
	const { open, setOpen, containerRef, handleMouseEnter, handleMouseLeave, handleBlur } =
		useHoverPopover();
	const maxIcons = 4;
	const visibleCitations = citations.slice(0, maxIcons);
	const remainingCount = Math.max(0, citations.length - maxIcons);

	const handleClick = (citation: SerializableCitation) => {
		const href = resolveSafeNavigationHref(citation.href);
		if (!href) return;
		if (onNavigate) {
			onNavigate(href, citation);
		} else {
			openSafeNavigationHref(href);
		}
	};

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: blur boundary for popover focus management
		<div ref={containerRef} onBlur={handleBlur} className="inline-flex">
			<Popover open={open}>
				<PopoverTrigger asChild>
					<button
						type="button"
						data-tool-ui-id={id}
						data-slot="citation-list"
						onMouseEnter={handleMouseEnter}
						onMouseLeave={handleMouseLeave}
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								setOpen(true);
							}
						}}
						className={cn(
							"isolate inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2",
							"bg-muted/40 outline-none",
							"transition-colors duration-150",
							"hover:bg-muted/70",
							"focus-visible:ring-ring focus-visible:ring-2",
							className
						)}
					>
						<div className="flex items-center">
							{visibleCitations.map((citation, index) => {
								const TypeIcon = TYPE_ICONS[citation.type ?? "webpage"] ?? Globe;
								return (
									<div
										key={citation.id}
										className={cn(
											"border-border bg-background dark:border-foreground/20 relative flex size-6 items-center justify-center rounded-full border shadow-xs",
											index > 0 && "-ml-2"
										)}
										style={{ zIndex: maxIcons - index }}
									>
										{citation.favicon ? (
										<NextImage
											src={citation.favicon}
											alt=""
											aria-hidden="true"
											width={18}
											height={18}
											className="size-4.5 rounded-full object-cover"
											unoptimized={true}
										/>
									) : (
										<TypeIcon className="text-muted-foreground size-3" aria-hidden="true" />
									)}	
									</div>
								);
							})}
							{remainingCount > 0 && (
								<div
									className="border-border bg-background dark:border-foreground/20 relative -ml-2 flex size-6 items-center justify-center rounded-full border shadow-xs"
									style={{ zIndex: 0 }}
								>
									<span className="text-muted-foreground text-[10px] font-medium tracking-tight">
										•••
									</span>
								</div>
							)}
						</div>
						<span className="text-muted-foreground text-sm tabular-nums">
							{citations.length} source{citations.length !== 1 && "s"}
						</span>
					</button>
				</PopoverTrigger>
				<PopoverContent
					side="bottom"
					align="start"
					className="w-80 p-1"
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
					onBlur={handleBlur}
					onEscapeKeyDown={() => setOpen(false)}
				>
					<div className="flex max-h-72 flex-col overflow-y-auto">
						{citations.map((citation) => (
							<OverflowItem
								key={citation.id}
								citation={citation}
								onClick={() => handleClick(citation)}
							/>
						))}
					</div>
				</PopoverContent>
			</Popover>
		</div>
	);
}
