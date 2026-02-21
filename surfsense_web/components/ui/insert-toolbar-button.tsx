"use client";

import type { DropdownMenuProps } from "@radix-ui/react-dropdown-menu";
import {
	ChevronRightIcon,
	FileCodeIcon,
	Heading1Icon,
	Heading2Icon,
	Heading3Icon,
	InfoIcon,
	ListIcon,
	ListOrderedIcon,
	MinusIcon,
	PilcrowIcon,
	PlusIcon,
	QuoteIcon,
	RadicalIcon,
	SquareIcon,
	SubscriptIcon,
	SuperscriptIcon,
	TableIcon,
} from "lucide-react";
import { KEYS } from "platejs";
import { type PlateEditor, useEditorRef } from "platejs/react";
import * as React from "react";
import { insertBlock, insertInlineElement } from "@/components/editor/transforms";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ToolbarButton, ToolbarMenuGroup } from "./toolbar";

type Group = {
	group: string;
	items: Item[];
};

type Item = {
	icon: React.ReactNode;
	value: string;
	onSelect: (editor: PlateEditor, value: string) => void;
	focusEditor?: boolean;
	label?: string;
};

const groups: Group[] = [
	{
		group: "Basic blocks",
		items: [
			{
				icon: <PilcrowIcon />,
				label: "Paragraph",
				value: KEYS.p,
			},
			{
				icon: <Heading1Icon />,
				label: "Heading 1",
				value: "h1",
			},
			{
				icon: <Heading2Icon />,
				label: "Heading 2",
				value: "h2",
			},
			{
				icon: <Heading3Icon />,
				label: "Heading 3",
				value: "h3",
			},
			{
				icon: <TableIcon />,
				label: "Table",
				value: KEYS.table,
			},
			{
				icon: <FileCodeIcon />,
				label: "Code block",
				value: KEYS.codeBlock,
			},
			{
				icon: <QuoteIcon />,
				label: "Quote",
				value: KEYS.blockquote,
			},
			{
				icon: <MinusIcon />,
				label: "Divider",
				value: KEYS.hr,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				insertBlock(editor, value);
			},
		})),
	},
	{
		group: "Lists",
		items: [
			{
				icon: <ListIcon />,
				label: "Bulleted list",
				value: KEYS.ul,
			},
			{
				icon: <ListOrderedIcon />,
				label: "Numbered list",
				value: KEYS.ol,
			},
			{
				icon: <SquareIcon />,
				label: "To-do list",
				value: KEYS.listTodo,
			},
			{
				icon: <ChevronRightIcon />,
				label: "Toggle list",
				value: KEYS.toggle,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				insertBlock(editor, value);
			},
		})),
	},
	{
		group: "Advanced",
		items: [
			{
				icon: <InfoIcon />,
				label: "Callout",
				value: KEYS.callout,
			},
			{
				focusEditor: false,
				icon: <RadicalIcon />,
				label: "Equation",
				value: KEYS.equation,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				if (item.value === KEYS.equation) {
					insertInlineElement(editor, value);
				} else {
					insertBlock(editor, value);
				}
			},
		})),
	},
	{
		group: "Marks",
		items: [
			{
				icon: <SuperscriptIcon />,
				label: "Superscript",
				value: KEYS.sup,
			},
			{
				icon: <SubscriptIcon />,
				label: "Subscript",
				value: KEYS.sub,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				editor.tf.toggleMark(value, {
					remove: value === KEYS.sup ? KEYS.sub : KEYS.sup,
				});
			},
		})),
	},
];

export function InsertToolbarButton(props: DropdownMenuProps) {
	const editor = useEditorRef();
	const [open, setOpen] = React.useState(false);

	return (
		<DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
			<DropdownMenuTrigger asChild>
				<ToolbarButton pressed={open} tooltip="Insert" isDropdown>
					<PlusIcon />
				</ToolbarButton>
			</DropdownMenuTrigger>

			<DropdownMenuContent
				className="z-[100] flex max-h-[60vh] min-w-0 flex-col overflow-y-auto dark:bg-neutral-800 dark:border dark:border-neutral-700"
				align="start"
			>
				{groups.map(({ group, items }) => (
					<React.Fragment key={group}>
						<ToolbarMenuGroup label={group}>
							{items.map(({ icon, label, value, onSelect, focusEditor }) => (
								<DropdownMenuItem
									key={value}
									onSelect={() => {
										onSelect(editor, value);
										if (focusEditor !== false) {
											editor.tf.focus();
										}
										setOpen(false);
									}}
									className="group"
								>
									<div className="flex items-center text-sm dark:text-white text-muted-foreground focus:text-accent-foreground group-aria-selected:text-accent-foreground">
										{icon}
										<span className="ml-2">{label || value}</span>
									</div>
								</DropdownMenuItem>
							))}
						</ToolbarMenuGroup>
					</React.Fragment>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
