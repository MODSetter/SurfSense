"use client";

import type { PlateLeafProps } from "platejs/react";
import { PlateLeaf } from "platejs/react";
import * as React from "react";

export function HighlightLeaf(props: PlateLeafProps) {
	return (
		<PlateLeaf {...props} as="mark" className="bg-yellow-200 dark:bg-yellow-800 text-inherit">
			{props.children}
		</PlateLeaf>
	);
}
