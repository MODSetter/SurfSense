"use client";

import type * as React from "react";

import { cn } from "@/lib/utils";

import { Toolbar } from "./toolbar";

export function FixedToolbar({
	children,
	className,
	...props
}: React.ComponentProps<typeof Toolbar>) {
	return (
		<Toolbar
			className={cn(
				"scrollbar-hide sticky top-0 left-0 z-50 w-full justify-between overflow-x-auto rounded-t-lg border-b bg-background/95 p-1 backdrop-blur supports-backdrop-filter:bg-background/60",
				className
			)}
			{...props}
		>
			{children}
		</Toolbar>
	);
}
