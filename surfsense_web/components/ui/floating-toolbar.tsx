"use client";

import {
	type FloatingToolbarState,
	flip,
	offset,
	useFloatingToolbar,
	useFloatingToolbarState,
} from "@platejs/floating";
import { useComposedRef } from "@udecode/cn";
import { KEYS } from "platejs";
import { useEditorId, useEventEditorValue, usePluginOption } from "platejs/react";
import type * as React from "react";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";

import { Toolbar } from "./toolbar";

export function FloatingToolbar({
	children,
	className,
	state,
	...props
}: React.ComponentProps<typeof Toolbar> & {
	state?: FloatingToolbarState;
}) {
	const editorId = useEditorId();
	const focusedEditorId = useEventEditorValue("focus");
	const isFloatingLinkOpen = !!usePluginOption({ key: KEYS.link }, "mode");
	const isMobile = useIsMobile();

	const floatingToolbarState = useFloatingToolbarState({
		editorId,
		focusedEditorId,
		hideToolbar: isFloatingLinkOpen,
		...state,
		floatingOptions: {
			middleware: [
				offset(12),
				flip({
					fallbackPlacements: ["top-start", "top-end", "bottom-start", "bottom-end"],
					padding: 12,
				}),
			],
			placement: "top",
			...state?.floatingOptions,
		},
	});

	const {
		clickOutsideRef,
		hidden,
		props: rootProps,
		ref: floatingRef,
	} = useFloatingToolbar(floatingToolbarState);

	const ref = useComposedRef<HTMLDivElement>(props.ref, floatingRef);

	if (hidden || isMobile) return null;

	return (
		<div ref={clickOutsideRef}>
			<Toolbar
				{...props}
				{...rootProps}
				ref={ref}
				className={cn(
					"scrollbar-hide absolute z-50 overflow-x-auto whitespace-nowrap rounded-md border bg-popover p-1 opacity-100 shadow-md print:hidden dark:bg-neutral-800 dark:border-neutral-700",
					"max-w-[80vw]",
					className
				)}
			>
				{children}
			</Toolbar>
		</div>
	);
}
