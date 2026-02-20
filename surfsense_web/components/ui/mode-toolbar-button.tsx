"use client";

import { BookOpenIcon, PenLineIcon } from "lucide-react";
import { usePlateState } from "platejs/react";

import { ToolbarButton } from "./toolbar";

export function ModeToolbarButton() {
	const [readOnly, setReadOnly] = usePlateState("readOnly");

	return (
		<ToolbarButton
			tooltip={readOnly ? "Click to edit" : "Click to view"}
			onClick={() => setReadOnly(!readOnly)}
		>
			{readOnly ? <BookOpenIcon /> : <PenLineIcon />}
		</ToolbarButton>
	);
}
