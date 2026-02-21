"use client";

import { getLinkAttributes } from "@platejs/link";

import type { TLinkElement } from "platejs";
import type { PlateElementProps } from "platejs/react";
import { PlateElement } from "platejs/react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function LinkElement(props: PlateElementProps<TLinkElement>) {
	return (
		<PlateElement
			{...props}
			as="a"
			className={cn(
				"font-medium text-blue-600 underline decoration-blue-600 underline-offset-4 hover:text-blue-800 dark:text-blue-400 dark:decoration-blue-400 dark:hover:text-blue-300"
			)}
			attributes={{
				...props.attributes,
				...getLinkAttributes(props.editor, props.element),
				onMouseOver: (e) => {
					e.stopPropagation();
				},
			}}
		>
			{props.children}
		</PlateElement>
	);
}
