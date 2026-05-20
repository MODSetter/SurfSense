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
				"scrollbar-hide sticky top-0 z-40 w-full shrink-0 justify-between overflow-x-auto border-b bg-background p-1",
				className
			)}
			{...props}
		>
			{children}
		</Toolbar>
	);
}
