"use client";

import { ExternalLink, Globe } from "lucide-react";
import NextImage from "next/image";
import { Button } from "@/components/ui/button";
import { openSafeNavigationHref, sanitizeHref } from "../shared/media";
import { cn } from "./_adapter";
import { CitationHoverPopover } from "./citation-hover-popover";
import type { CitationVariant, SerializableCitation } from "./schema";
import { TYPE_ICONS } from "./type-icons";

const FALLBACK_LOCALE = "en-US";

function extractDomain(url: string): string | undefined {
	try {
		const urlObj = new URL(url);
		return urlObj.hostname.replace(/^www\./, "");
	} catch {
		return undefined;
	}
}

function formatDate(isoString: string, locale: string): string {
	try {
		const date = new Date(isoString);
		return date.toLocaleDateString(locale, {
			year: "numeric",
			month: "short",
		});
	} catch {
		return isoString;
	}
}

export interface CitationProps extends SerializableCitation {
	variant?: CitationVariant;
	className?: string;
	onNavigate?: (href: string, citation: SerializableCitation) => void;
}

export function Citation(props: CitationProps) {
	const { variant = "default", className, onNavigate, ...serializable } = props;

	const {
		id,
		href: rawHref,
		title,
		snippet,
		domain: providedDomain,
		favicon,
		author,
		publishedAt,
		type = "webpage",
		locale: providedLocale,
	} = serializable;

	const locale = providedLocale ?? FALLBACK_LOCALE;
	const sanitizedHref = sanitizeHref(rawHref);
	const domain = providedDomain ?? extractDomain(rawHref);

	const citationData: SerializableCitation = {
		...serializable,
		href: sanitizedHref ?? rawHref,
		domain,
		locale,
	};

	const TypeIcon = TYPE_ICONS[type] ?? Globe;

	const handleClick = () => {
		if (!sanitizedHref) return;
		if (onNavigate) {
			onNavigate(sanitizedHref, citationData);
		} else {
			openSafeNavigationHref(sanitizedHref);
		}
	};

	const iconElement = favicon ? (
		<NextImage
			src={favicon}
			alt=""
			aria-hidden="true"
			width={16}
			height={16}
			className="bg-muted size-3.5 shrink-0 rounded object-cover"
			unoptimized={true}
		/>
	) : (
		<TypeIcon className="size-3.5 shrink-0 opacity-60" aria-hidden="true" />
	);

	// Inline variant: compact chip with hover popover
	if (variant === "inline") {
		return (
			<CitationHoverPopover
				id={id}
				contentClassName="w-72 cursor-pointer p-0"
				onContentClick={handleClick}
				trigger={(hoverProps) => (
					<Button
						variant="ghost"
						type="button"
						aria-label={title}
						data-tool-ui-id={id}
						data-slot="citation"
						onClick={handleClick}
						{...hoverProps}
						className={cn(
							"h-auto cursor-pointer gap-1.5 rounded-md px-2 py-1",
							"bg-muted/60 text-sm outline-none",
							"transition-colors duration-150",
							"hover:bg-accent hover:text-accent-foreground",
							"focus-visible:ring-ring focus-visible:ring-2",
							className
						)}
					>
						{iconElement}
						<span className="text-muted-foreground">{domain}</span>
					</Button>
				)}
			>
				<div className="hover:bg-accent hover:text-accent-foreground flex flex-col gap-2 p-3 transition-colors">
					<div className="flex items-start gap-2">
						{iconElement}
						<span className="text-muted-foreground text-xs">{domain}</span>
					</div>
					<p className="text-sm leading-snug font-medium">{title}</p>
					{snippet && (
						<p className="text-muted-foreground line-clamp-2 text-xs leading-relaxed">
							{snippet}
						</p>
					)}
				</div>
			</CitationHoverPopover>
		);
	}

	const cardClassName = cn(
		"group @container relative isolate flex w-full min-w-0 flex-col overflow-hidden rounded-xl",
		"border-border bg-card border text-sm shadow-xs",
		"transition-colors duration-150",
		sanitizedHref && [
			"cursor-pointer no-underline",
			"hover:border-foreground/25",
			"focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
		]
	);

	const cardContent = (
		<div className="flex flex-col gap-2 p-4">
			<div className="text-muted-foreground flex min-w-0 items-center justify-between gap-1.5 text-xs">
				<div className="flex min-w-0 items-center gap-1.5">
					{iconElement}
					<span className="truncate font-medium">{domain}</span>
					{(author || publishedAt) && (
						<span className="opacity-70">
							<span className="opacity-60"> — </span>
							{author}
							{author && publishedAt && ", "}
							{publishedAt && (
								<time dateTime={publishedAt} className="tabular-nums">
									{formatDate(publishedAt, locale)}
								</time>
							)}
						</span>
					)}
				</div>
				{sanitizedHref && (
					<ExternalLink className="size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
				)}
			</div>

			<h3 className="text-foreground text-[15px] leading-snug font-medium text-pretty">
				<span className="group-hover:decoration-foreground/30 line-clamp-2 group-hover:underline group-hover:underline-offset-2">
					{title}
				</span>
			</h3>

			{snippet && (
				<p className="text-muted-foreground text-[13px] leading-relaxed text-pretty">
					<span className="line-clamp-3">{snippet}</span>
				</p>
			)}
		</div>
	);

	// Default variant: full card
	return (
		<article
			className={cn("relative w-full max-w-md min-w-72", className)}
			lang={locale}
			data-tool-ui-id={id}
			data-slot="citation"
		>
			{sanitizedHref ? (
				<a
					href={sanitizedHref}
					target="_blank"
					rel="noopener noreferrer"
					className={cardClassName}
					onClick={(event) => {
						event.preventDefault();
						handleClick();
					}}
				>
					{cardContent}
				</a>
			) : (
				<div className={cardClassName}>{cardContent}</div>
			)}
		</article>
	);
}
