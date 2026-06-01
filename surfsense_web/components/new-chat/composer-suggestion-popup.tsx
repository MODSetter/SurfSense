"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { PopoverContent } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function ComposerSuggestionPopoverContent({
	className,
	align = "start",
	sideOffset = 6,
	collisionPadding = 12,
	onOpenAutoFocus,
	onCloseAutoFocus,
	style,
	...props
}: React.ComponentProps<typeof PopoverContent>) {
	return (
		<PopoverContent
			align={align}
			sideOffset={sideOffset}
			collisionPadding={collisionPadding}
			onOpenAutoFocus={(event) => {
				event.preventDefault();
				onOpenAutoFocus?.(event);
			}}
			onCloseAutoFocus={(event) => {
				event.preventDefault();
				onCloseAutoFocus?.(event);
			}}
			className={cn(
				"w-[232px] select-none overflow-hidden rounded-md border border-popover-border bg-popover p-0 text-popover-foreground shadow-md sm:w-[264px]",
				"data-[state=open]:!animate-none data-[state=closed]:!animate-none data-[state=open]:!duration-0 data-[state=closed]:!duration-0",
				className
			)}
			style={{ ...style, animation: "none" }}
			{...props}
		/>
	);
}

const ComposerSuggestionList = React.forwardRef<
	HTMLDivElement,
	React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
	<div
		ref={ref}
		className={cn("max-h-[144px] overflow-y-auto sm:max-h-[200px]", className)}
		{...props}
	/>
));
ComposerSuggestionList.displayName = "ComposerSuggestionList";

function ComposerSuggestionGroup({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
	return <div className={cn("px-1.5 py-1.5", className)} {...props} />;
}

function ComposerSuggestionGroupHeading({
	className,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn("px-2 py-1 text-xs font-semibold text-muted-foreground", className)}
			{...props}
		/>
	);
}

function ComposerSuggestionHeader({
	className,
	icon,
	children,
	...props
}: React.HTMLAttributes<HTMLDivElement> & { icon?: React.ReactNode }) {
	return (
		<div
			className={cn(
				"flex items-center gap-1.5 px-2 py-1 text-xs font-semibold text-muted-foreground",
				className
			)}
			{...props}
		>
			{icon ? <span className="shrink-0 text-current [&_svg]:size-3.5">{icon}</span> : null}
			{children}
		</div>
	);
}

const ComposerSuggestionItem = React.forwardRef<
	HTMLButtonElement,
	Omit<React.ComponentProps<typeof Button>, "variant"> & {
		icon?: React.ReactNode;
		selected?: boolean;
		muted?: boolean;
	}
>(({ className, children, icon, selected, muted, disabled, ...props }, ref) => (
	<Button
		ref={ref}
		type="button"
		variant="ghost"
		disabled={disabled}
		className={cn(
			"h-auto w-full justify-start gap-1.5 rounded-md px-2 py-1 text-left text-xs font-normal transition-colors",
			disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
			muted && !selected && "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
			selected && "bg-accent text-accent-foreground",
			className
		)}
		{...props}
	>
		{icon ? <span className="shrink-0 text-current [&_svg]:size-3.5">{icon}</span> : null}
		{children}
	</Button>
));
ComposerSuggestionItem.displayName = "ComposerSuggestionItem";

function ComposerSuggestionSeparator({
	className,
	...props
}: React.ComponentProps<typeof Separator>) {
	return (
		<div className={cn("my-0.5 px-2.5", className)}>
			<Separator className="bg-popover-border" {...props} />
		</div>
	);
}

function ComposerSuggestionMessage({
	className,
	children,
	variant = "muted",
}: React.HTMLAttributes<HTMLParagraphElement> & { variant?: "muted" | "destructive" }) {
	return (
		<div className="px-1.5 py-1">
			<p
				className={cn(
					"px-2 py-1 text-xs",
					variant === "destructive" ? "text-destructive" : "text-muted-foreground",
					className
				)}
			>
				{children}
			</p>
		</div>
	);
}

function ComposerSuggestionSkeleton({
	rows = 5,
	mobileRows = 3,
}: {
	rows?: number;
	mobileRows?: number;
}) {
	return (
		<div className="px-1.5 py-1">
			<div className="px-2 py-1">
				<Skeleton className="h-3.5 w-20" />
			</div>
			{Array.from({ length: rows }, (_, index) => `skeleton-row-${index}`).map((id, index) => (
				<div
					key={id}
					className={cn(
						"flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left",
						index >= mobileRows && "hidden sm:flex"
					)}
				>
					<span className="shrink-0">
						<Skeleton className="size-3.5" />
					</span>
					<span className="flex-1 text-xs">
						<Skeleton className="h-4" style={{ width: `${60 + ((index * 7) % 30)}%` }} />
					</span>
				</div>
			))}
		</div>
	);
}

export {
	ComposerSuggestionPopoverContent,
	ComposerSuggestionList,
	ComposerSuggestionGroup,
	ComposerSuggestionGroupHeading,
	ComposerSuggestionHeader,
	ComposerSuggestionItem,
	ComposerSuggestionSeparator,
	ComposerSuggestionMessage,
	ComposerSuggestionSkeleton,
};
