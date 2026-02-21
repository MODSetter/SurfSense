"use client";

import { useToggleButton, useToggleButtonState } from "@platejs/toggle/react";
import { ChevronRightIcon } from "lucide-react";
import { PlateElement, type PlateElementProps } from "platejs/react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function ToggleElement({ children, ...props }: PlateElementProps) {
	const element = props.element;
	const state = useToggleButtonState(element.id as string);
	const { buttonProps, open } = useToggleButton(state);

	return (
		<PlateElement {...props} className="relative py-1 pl-6">
			<button
				className={cn(
					"absolute top-1.5 left-0 flex size-6 cursor-pointer select-none items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
				)}
				contentEditable={false}
				type="button"
				{...buttonProps}
			>
				<ChevronRightIcon
					className={cn("size-4 transition-transform duration-200", open && "rotate-90")}
				/>
			</button>
			<div>{children}</div>
		</PlateElement>
	);
}
