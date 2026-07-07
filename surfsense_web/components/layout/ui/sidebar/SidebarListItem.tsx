"use client";

import type React from "react";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type SidebarListItemElementProps = React.HTMLAttributes<HTMLDivElement>;

interface SidebarListItemProps extends SidebarListItemElementProps {
	active?: boolean;
	dragging?: boolean;
	interactive?: boolean;
}

export const SidebarListItem = forwardRef<HTMLDivElement, SidebarListItemProps>(
	({ active, dragging, interactive = true, className, children, ...props }, ref) => (
		<div
			ref={ref}
			className={sidebarListItemClassName({ active, dragging, interactive, className })}
			{...props}
		>
			{children}
		</div>
	)
);

SidebarListItem.displayName = "SidebarListItem";

export function sidebarListItemClassName({
	active,
	dragging,
	interactive = true,
	className,
}: {
	active?: boolean;
	dragging?: boolean;
	interactive?: boolean;
	className?: string;
}) {
	return cn(
		"group group/sidebar-list-item flex h-8 w-full items-center rounded-md text-left text-sm select-none",
		interactive && "cursor-pointer hover:bg-accent hover:text-accent-foreground",
		active && "bg-accent text-accent-foreground",
		dragging && "opacity-40",
		className
	);
}
