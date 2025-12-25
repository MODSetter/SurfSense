"use client";

import {
	ChevronDown,
	Circle,
	File,
	FileAudio,
	FileCode,
	FileImage,
	FileSpreadsheet,
	FileText,
	FileVideo,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

/**
 * Custom hook for entrance animation
 * Returns true after mount to trigger CSS transitions
 */
function useEntranceAnimation(delay = 0) {
	const [isVisible, setIsVisible] = useState(false);

	useEffect(() => {
		const timer = setTimeout(() => setIsVisible(true), delay);
		return () => clearTimeout(timer);
	}, [delay]);

	return isVisible;
}

/**
 * Get file icon based on file extension (all icons are muted/gray)
 */
function getFileIcon(name: string): React.ReactNode {
	const ext = name.split(".").pop()?.toLowerCase() || "";

	// PDF / Word documents
	if (ext === "pdf" || ["doc", "docx"].includes(ext)) {
		return <FileText className="size-3.5" />;
	}
	// Spreadsheets
	if (["xls", "xlsx", "csv"].includes(ext)) {
		return <FileSpreadsheet className="size-3.5" />;
	}
	// Images
	if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) {
		return <FileImage className="size-3.5" />;
	}
	// Audio
	if (["mp3", "wav", "m4a", "ogg", "webm"].includes(ext)) {
		return <FileAudio className="size-3.5" />;
	}
	// Video
	if (["mp4", "mov", "avi", "mkv"].includes(ext)) {
		return <FileVideo className="size-3.5" />;
	}
	// Code files
	if (["js", "ts", "tsx", "jsx", "py", "html", "css", "json", "md"].includes(ext)) {
		return <FileCode className="size-3.5" />;
	}
	// Default
	return <File className="size-3.5" />;
}

/**
 * Compact attachment tile component - matches the chat UI style
 */
const AttachmentTile: React.FC<{ name: string }> = ({ name }) => {
	const icon = getFileIcon(name);

	return (
		<span
			className="inline-flex items-center gap-1.5 rounded-lg bg-muted px-2 py-1 text-xs text-muted-foreground"
			title={name}
		>
			<span className="shrink-0">{icon}</span>
			<span className="truncate max-w-[120px]">{name}</span>
		</span>
	);
};

/**
 * Parse text and render bracketed items (like [filename.pdf]) as styled tiles
 */
function parseAndRenderWithBadges(text: string): React.ReactNode {
	// Match patterns like [filename.ext] or [N files] or [N documents]
	const regex = /\[([^\]]+)\]/g;
	const matches = Array.from(text.matchAll(regex));

	if (matches.length === 0) {
		return text;
	}

	const parts: React.ReactNode[] = [];
	let lastIndex = 0;

	for (const match of matches) {
		const matchIndex = match.index ?? 0;

		// Add text before the match
		if (matchIndex > lastIndex) {
			parts.push(text.slice(lastIndex, matchIndex));
		}

		const content = match[1];

		// Render as a compact tile matching chat UI style with file-type colors
		parts.push(<AttachmentTile key={`tile-${matchIndex}`} name={content} />);

		lastIndex = matchIndex + match[0].length;
	}

	// Add remaining text
	if (lastIndex < text.length) {
		parts.push(text.slice(lastIndex));
	}

	return parts;
}

export type ChainOfThoughtItemProps = React.ComponentProps<"div">;

export const ChainOfThoughtItem = ({ children, className, ...props }: ChainOfThoughtItemProps) => (
	<div className={cn("text-muted-foreground text-sm flex flex-wrap items-center gap-1", className)} {...props}>
		{typeof children === "string" ? parseAndRenderWithBadges(children) : children}
	</div>
);

export type ChainOfThoughtTriggerProps = React.ComponentProps<typeof CollapsibleTrigger> & {
	leftIcon?: React.ReactNode;
	swapIconOnHover?: boolean;
};

export const ChainOfThoughtTrigger = ({
	children,
	className,
	leftIcon,
	swapIconOnHover = true,
	...props
}: ChainOfThoughtTriggerProps) => (
	<CollapsibleTrigger
		className={cn(
			"group text-muted-foreground hover:text-foreground flex cursor-pointer items-center justify-start gap-1 text-left text-sm transition-colors",
			className
		)}
		{...props}
	>
		<div className="flex items-center gap-2">
			{leftIcon ? (
				<span className="relative inline-flex size-4 items-center justify-center">
					<span className={cn("transition-opacity", swapIconOnHover && "group-hover:opacity-0")}>
						{leftIcon}
					</span>
					{swapIconOnHover && (
						<ChevronDown className="absolute size-4 opacity-0 transition-opacity group-hover:opacity-100 group-data-[state=open]:rotate-180" />
					)}
				</span>
			) : (
				<span className="relative inline-flex size-4 items-center justify-center">
					<Circle className="size-2 fill-current" />
				</span>
			)}
			<span>{children}</span>
		</div>
		{!leftIcon && (
			<ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" />
		)}
	</CollapsibleTrigger>
);

export type ChainOfThoughtContentProps = React.ComponentProps<typeof CollapsibleContent>;

export const ChainOfThoughtContent = ({
	children,
	className,
	...props
}: ChainOfThoughtContentProps) => {
	return (
		<CollapsibleContent
			className={cn(
				"text-popover-foreground data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden",
				className
			)}
			{...props}
		>
			<div className="grid grid-cols-[min-content_minmax(0,1fr)] gap-x-4">
				{/* Animated vertical connection line */}
				<div
					className={cn(
						"ml-1.75 w-px bg-primary/20 group-data-[last=true]:hidden",
						"animate-in fade-in slide-in-from-top-1 duration-300"
					)}
				/>
				<div className="ml-1.75 h-full w-px bg-transparent group-data-[last=false]:hidden" />
				<div className="mt-2 space-y-1.5">
					{React.Children.map(children, (child, index) => {
						const key = React.isValidElement(child) ? child.key : `cot-item-${index}`;
						return (
							<div
								key={key}
								className="animate-in fade-in slide-in-from-left-2 duration-200"
								style={{ animationDelay: `${index * 50}ms`, animationFillMode: "backwards" }}
							>
								{child}
							</div>
						);
					})}
				</div>
			</div>
		</CollapsibleContent>
	);
};

export type ChainOfThoughtProps = {
	children: React.ReactNode;
	className?: string;
};

export function ChainOfThought({ children, className }: ChainOfThoughtProps) {
	const childrenArray = React.Children.toArray(children);

	return (
		<div className={cn("space-y-0", className)}>
			{childrenArray.map((child, index) => {
				// React.Children.toArray assigns stable keys to each child
				const key = React.isValidElement(child) ? child.key : `cot-step-${index}`;
				return (
					<React.Fragment key={key}>
						{React.isValidElement(child) &&
							React.cloneElement(child as React.ReactElement<ChainOfThoughtStepProps>, {
								isLast: index === childrenArray.length - 1,
								stepIndex: index,
							})}
					</React.Fragment>
				);
			})}
		</div>
	);
}

export type ChainOfThoughtStepProps = {
	children: React.ReactNode;
	className?: string;
	isLast?: boolean;
	/** Index of the step for staggered animation */
	stepIndex?: number;
};

export const ChainOfThoughtStep = ({
	children,
	className,
	isLast = false,
	stepIndex = 0,
	...props
}: ChainOfThoughtStepProps & React.ComponentProps<typeof Collapsible>) => {
	// Staggered entrance animation based on step index
	const isVisible = useEntranceAnimation(stepIndex * 50);

	return (
		<Collapsible
			className={cn(
				"group transition-all duration-300 ease-out",
				// Fade and slide in animation
				isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
				className
			)}
			data-last={isLast}
			{...props}
		>
			{children}
			{/* Animated connection line to next step */}
			<div className="flex justify-start group-data-[last=true]:hidden">
				<div
					className={cn(
						"ml-1.75 w-px bg-primary/20 transition-all duration-500 ease-out origin-top",
						// Animate line height from 0 to full
						isVisible ? "h-4 scale-y-100" : "h-0 scale-y-0"
					)}
					style={{ transitionDelay: `${stepIndex * 50 + 150}ms` }}
				/>
			</div>
		</Collapsible>
	);
};
