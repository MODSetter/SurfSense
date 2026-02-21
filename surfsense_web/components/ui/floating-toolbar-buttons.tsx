"use client";

import { BoldIcon, Code2Icon, ItalicIcon, StrikethroughIcon, UnderlineIcon } from "lucide-react";
import { KEYS } from "platejs";
import { useEditorReadOnly } from "platejs/react";
import * as React from "react";

import { LinkToolbarButton } from "./link-toolbar-button";
import { MarkToolbarButton } from "./mark-toolbar-button";
import { ToolbarGroup } from "./toolbar";
import { TurnIntoToolbarButton } from "./turn-into-toolbar-button";

export function FloatingToolbarButtons() {
	const readOnly = useEditorReadOnly();

	if (readOnly) return null;

	return (
		<>
			<ToolbarGroup>
				<TurnIntoToolbarButton tooltip={false} />

				<MarkToolbarButton nodeType={KEYS.bold}>
					<BoldIcon />
				</MarkToolbarButton>

				<MarkToolbarButton nodeType={KEYS.italic}>
					<ItalicIcon />
				</MarkToolbarButton>

				<MarkToolbarButton nodeType={KEYS.underline}>
					<UnderlineIcon />
				</MarkToolbarButton>

				<MarkToolbarButton nodeType={KEYS.strikethrough}>
					<StrikethroughIcon />
				</MarkToolbarButton>

				<MarkToolbarButton nodeType={KEYS.code}>
					<Code2Icon />
				</MarkToolbarButton>

				<LinkToolbarButton tooltip={false} />
			</ToolbarGroup>
		</>
	);
}
