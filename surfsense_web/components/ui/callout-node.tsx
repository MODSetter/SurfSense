"use client";

import { CalloutPlugin } from "@platejs/callout/react";
import { cva } from "class-variance-authority";
import type { TCalloutElement } from "platejs";
import { PlateElement, type PlateElementProps, useEditorPlugin } from "platejs/react";
import * as React from "react";

import { cn } from "@/lib/utils";

const calloutVariants = cva("my-1 flex w-full items-start gap-2 rounded-lg border p-4", {
	defaultVariants: {
		variant: "info",
	},
	variants: {
		variant: {
			info: "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/50",
			warning: "border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950/50",
			error: "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/50",
			success: "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950/50",
			note: "border-muted bg-muted/50",
			tip: "border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950/50",
		},
	},
});

const calloutIcons: Record<string, string> = {
	info: "💡",
	warning: "⚠️",
	error: "🚨",
	success: "✅",
	note: "📝",
	tip: "💜",
};

const variantCycle = ["info", "warning", "error", "success", "note", "tip"] as const;

export function CalloutElement({ children, ...props }: PlateElementProps<TCalloutElement>) {
	const { editor } = useEditorPlugin(CalloutPlugin);
	const element = props.element;
	const variant = element.variant || "info";
	const icon = element.icon || calloutIcons[variant] || "💡";

	const cycleVariant = React.useCallback(() => {
		const currentIndex = variantCycle.indexOf(variant as (typeof variantCycle)[number]);
		const nextIndex = (currentIndex + 1) % variantCycle.length;
		const nextVariant = variantCycle[nextIndex];

		editor.tf.setNodes(
			{
				variant: nextVariant,
				icon: calloutIcons[nextVariant],
			},
			{ at: props.path }
		);
	}, [editor, variant, props.path]);

	return (
		<PlateElement
			{...props}
			className={cn(calloutVariants({ variant: variant as any }), props.className)}
		>
			<button
				className="mt-0.5 shrink-0 cursor-pointer select-none text-lg leading-none"
				contentEditable={false}
				onClick={cycleVariant}
				type="button"
				aria-label="Change callout type"
			>
				{icon}
			</button>
			<div className="min-w-0 flex-1">{children}</div>
		</PlateElement>
	);
}
