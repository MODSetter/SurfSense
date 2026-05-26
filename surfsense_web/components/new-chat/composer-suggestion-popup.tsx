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
	sideOffset = 8,
	onOpenAutoFocus,
	onCloseAutoFocus,
	...props
}: React.ComponentProps<typeof PopoverContent>) {
	return (
		<PopoverContent
			align={align}
			sideOffset={sideOffset}
			onOpenAutoFocus={(event) => {
				event.preventDefault();
				onOpenAutoFocus?.(event);
			}}
			onCloseAutoFocus={(event) => {
				event.preventDefault();
				onCloseAutoFocus?.(event);
			}}
			className={cn(
				"w-[280px] overflow-hidden rounded-xl border border-popover-border bg-popover p-0 text-popover-foreground shadow-2xl sm:w-[320px]",
				className
			)}
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
		className={cn("max-h-[180px] overflow-y-auto sm:max-h-[280px]", className)}
		{...props}
	/>
));
ComposerSuggestionList.displayName = "ComposerSuggestionList";

function ComposerSuggestionGroup({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
	return <div className={cn("px-2 py-1", className)} {...props} />;
}

function ComposerSuggestionGroupHeading({
	className,
	...props
}: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn("px-3 py-2 text-xs font-bold text-muted-foreground/55", className)}
			{...props}
		/>
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
			"h-auto w-full justify-start gap-2 rounded-md px-3 py-2 text-left text-sm font-normal transition-colors",
			disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
			muted && !selected && "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
			selected && "bg-accent text-accent-foreground",
			className
		)}
		{...props}
	>
		{icon ? <span className="shrink-0 text-muted-foreground">{icon}</span> : null}
		{children}
	</Button>
));
ComposerSuggestionItem.displayName = "ComposerSuggestionItem";

function ComposerSuggestionSeparator({ className, ...props }: React.ComponentProps<typeof Separator>) {
	return (
		<div className={cn("my-1 px-4", className)}>
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
		<div className="px-2 py-1">
			<p
				className={cn(
					"px-3 py-2 text-xs",
					variant === "destructive" ? "text-destructive" : "text-muted-foreground",
					className
				)}
			>
				{children}
			</p>
		</div>
	);
}

function ComposerSuggestionSkeleton() {
	return (
		<div className="px-2 py-1">
			<div className="px-3 py-2">
				<Skeleton className="h-[16px] w-24" />
			</div>
			{["a", "b", "c", "d", "e"].map((id, index) => (
				<div
					key={id}
					className={cn(
						"flex w-full items-center gap-2 rounded-md px-3 py-2 text-left",
						index >= 3 && "hidden sm:flex"
					)}
				>
					<span className="shrink-0">
						<Skeleton className="size-4" />
					</span>
					<span className="flex-1 text-sm">
						<Skeleton className="h-[20px]" style={{ width: `${60 + ((index * 7) % 30)}%` }} />
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
	ComposerSuggestionItem,
	ComposerSuggestionSeparator,
	ComposerSuggestionMessage,
	ComposerSuggestionSkeleton,
};
