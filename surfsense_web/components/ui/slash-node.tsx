"use client";

import { SlashInputPlugin } from "@platejs/slash-command/react";
import {
	ChevronRightIcon,
	Code2Icon,
	FileCodeIcon,
	Heading1Icon,
	Heading2Icon,
	Heading3Icon,
	InfoIcon,
	ListIcon,
	ListOrderedIcon,
	MinusIcon,
	PilcrowIcon,
	QuoteIcon,
	RadicalIcon,
	SquareIcon,
	TableIcon,
} from "lucide-react";
import { KEYS } from "platejs";
import type { PlateElementProps } from "platejs/react";
import { PlateElement, useEditorRef } from "platejs/react";
import type * as React from "react";
import { insertBlock, insertInlineElement } from "@/components/editor/transforms";
import {
	InlineCombobox,
	InlineComboboxContent,
	InlineComboboxEmpty,
	InlineComboboxGroup,
	InlineComboboxGroupLabel,
	InlineComboboxInput,
	InlineComboboxItem,
} from "@/components/ui/inline-combobox";

interface SlashCommandItem {
	icon: React.ReactNode;
	keywords: string[];
	label: string;
	value: string;
	onSelect: (editor: any) => void;
}

const slashCommandGroups: { heading: string; items: SlashCommandItem[] }[] = [
	{
		heading: "Basic Blocks",
		items: [
			{
				icon: <PilcrowIcon />,
				keywords: ["paragraph", "text", "plain"],
				label: "Text",
				value: "text",
				onSelect: (editor) => insertBlock(editor, KEYS.p),
			},
			{
				icon: <Heading1Icon />,
				keywords: ["title", "h1", "heading"],
				label: "Heading 1",
				value: "heading1",
				onSelect: (editor) => insertBlock(editor, "h1"),
			},
			{
				icon: <Heading2Icon />,
				keywords: ["subtitle", "h2", "heading"],
				label: "Heading 2",
				value: "heading2",
				onSelect: (editor) => insertBlock(editor, "h2"),
			},
			{
				icon: <Heading3Icon />,
				keywords: ["subtitle", "h3", "heading"],
				label: "Heading 3",
				value: "heading3",
				onSelect: (editor) => insertBlock(editor, "h3"),
			},
			{
				icon: <QuoteIcon />,
				keywords: ["citation", "blockquote"],
				label: "Quote",
				value: "quote",
				onSelect: (editor) => insertBlock(editor, KEYS.blockquote),
			},
			{
				icon: <MinusIcon />,
				keywords: ["divider", "separator", "line"],
				label: "Divider",
				value: "divider",
				onSelect: (editor) => insertBlock(editor, KEYS.hr),
			},
		],
	},
	{
		heading: "Lists",
		items: [
			{
				icon: <ListIcon />,
				keywords: ["unordered", "ul", "bullet"],
				label: "Bulleted list",
				value: "bulleted-list",
				onSelect: (editor) => insertBlock(editor, KEYS.ul),
			},
			{
				icon: <ListOrderedIcon />,
				keywords: ["ordered", "ol", "numbered"],
				label: "Numbered list",
				value: "numbered-list",
				onSelect: (editor) => insertBlock(editor, KEYS.ol),
			},
			{
				icon: <SquareIcon />,
				keywords: ["checklist", "task", "checkbox", "todo"],
				label: "To-do list",
				value: "todo-list",
				onSelect: (editor) => insertBlock(editor, KEYS.listTodo),
			},
		],
	},
	{
		heading: "Advanced",
		items: [
			{
				icon: <TableIcon />,
				keywords: ["table", "grid"],
				label: "Table",
				value: "table",
				onSelect: (editor) => insertBlock(editor, KEYS.table),
			},
			{
				icon: <FileCodeIcon />,
				keywords: ["code", "codeblock", "snippet"],
				label: "Code block",
				value: "code-block",
				onSelect: (editor) => insertBlock(editor, KEYS.codeBlock),
			},
			{
				icon: <InfoIcon />,
				keywords: ["callout", "note", "info", "warning", "tip"],
				label: "Callout",
				value: "callout",
				onSelect: (editor) => insertBlock(editor, KEYS.callout),
			},
			{
				icon: <ChevronRightIcon />,
				keywords: ["toggle", "collapsible", "expand"],
				label: "Toggle",
				value: "toggle",
				onSelect: (editor) => insertBlock(editor, KEYS.toggle),
			},
			{
				icon: <RadicalIcon />,
				keywords: ["equation", "math", "formula", "latex"],
				label: "Equation",
				value: "equation",
				onSelect: (editor) => insertInlineElement(editor, KEYS.equation),
			},
		],
	},
	{
		heading: "Inline",
		items: [
			{
				icon: <Code2Icon />,
				keywords: ["link", "url", "href"],
				label: "Link",
				value: "link",
				onSelect: (editor) => insertInlineElement(editor, KEYS.link),
			},
		],
	},
];

export function SlashInputElement({ children, ...props }: PlateElementProps) {
	const editor = useEditorRef();

	return (
		<PlateElement {...props} as="span">
			<InlineCombobox element={props.element} trigger="/">
				<InlineComboboxInput />

				<InlineComboboxContent className="dark:bg-neutral-800 dark:border dark:border-neutral-700">
					<InlineComboboxEmpty>No results found.</InlineComboboxEmpty>

					{slashCommandGroups.map(({ heading, items }) => (
						<InlineComboboxGroup key={heading}>
							<InlineComboboxGroupLabel>{heading}</InlineComboboxGroupLabel>

							{items.map(({ icon, keywords, label, value, onSelect }) => (
								<InlineComboboxItem
									key={value}
									className="flex items-center gap-3 px-2 py-1.5"
									keywords={keywords}
									label={label}
									value={value}
									group={heading}
									onClick={() => {
										onSelect(editor);
										editor.tf.focus();
									}}
								>
									<span className="flex size-5 items-center justify-center text-muted-foreground">
										{icon}
									</span>
									{label}
								</InlineComboboxItem>
							))}
						</InlineComboboxGroup>
					))}
				</InlineComboboxContent>
			</InlineCombobox>

			{children}
		</PlateElement>
	);
}
