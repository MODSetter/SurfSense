"use client";

import type { DropdownMenuProps } from "@radix-ui/react-dropdown-menu";
import { DropdownMenuItemIndicator } from "@radix-ui/react-dropdown-menu";
import {
	CheckIcon,
	ChevronRightIcon,
	FileCodeIcon,
	Heading1Icon,
	Heading2Icon,
	Heading3Icon,
	Heading4Icon,
	Heading5Icon,
	Heading6Icon,
	InfoIcon,
	ListIcon,
	ListOrderedIcon,
	PilcrowIcon,
	QuoteIcon,
	SquareIcon,
} from "lucide-react";
import type { TElement } from "platejs";
import { KEYS } from "platejs";
import { useEditorRef, useSelectionFragmentProp } from "platejs/react";
import * as React from "react";
import { getBlockType, setBlockType } from "@/components/editor/transforms";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuRadioItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ToolbarButton, ToolbarMenuGroup } from "./toolbar";

export const turnIntoItems = [
	{
		icon: <PilcrowIcon />,
		keywords: ["paragraph"],
		label: "Text",
		value: KEYS.p,
	},
	{
		icon: <Heading1Icon />,
		keywords: ["title", "h1"],
		label: "Heading 1",
		value: "h1",
	},
	{
		icon: <Heading2Icon />,
		keywords: ["subtitle", "h2"],
		label: "Heading 2",
		value: "h2",
	},
	{
		icon: <Heading3Icon />,
		keywords: ["subtitle", "h3"],
		label: "Heading 3",
		value: "h3",
	},
	{
		icon: <Heading4Icon />,
		keywords: ["subtitle", "h4"],
		label: "Heading 4",
		value: "h4",
	},
	{
		icon: <Heading5Icon />,
		keywords: ["subtitle", "h5"],
		label: "Heading 5",
		value: "h5",
	},
	{
		icon: <Heading6Icon />,
		keywords: ["subtitle", "h6"],
		label: "Heading 6",
		value: "h6",
	},
	{
		icon: <ListIcon />,
		keywords: ["unordered", "ul", "-"],
		label: "Bulleted list",
		value: KEYS.ul,
	},
	{
		icon: <ListOrderedIcon />,
		keywords: ["ordered", "ol", "1"],
		label: "Numbered list",
		value: KEYS.ol,
	},
	{
		icon: <SquareIcon />,
		keywords: ["checklist", "task", "checkbox", "[]"],
		label: "To-do list",
		value: KEYS.listTodo,
	},
	{
		icon: <FileCodeIcon />,
		keywords: ["```"],
		label: "Code",
		value: KEYS.codeBlock,
	},
	{
		icon: <QuoteIcon />,
		keywords: ["citation", "blockquote", ">"],
		label: "Quote",
		value: KEYS.blockquote,
	},
	{
		icon: <InfoIcon />,
		keywords: ["callout", "note", "info", "warning", "tip"],
		label: "Callout",
		value: KEYS.callout,
	},
	{
		icon: <ChevronRightIcon />,
		keywords: ["toggle", "collapsible", "expand"],
		label: "Toggle",
		value: KEYS.toggle,
	},
];

export function TurnIntoToolbarButton({
	tooltip = "Turn into",
	...props
}: DropdownMenuProps & { tooltip?: React.ReactNode }) {
	const editor = useEditorRef();
	const [open, setOpen] = React.useState(false);

	const value = useSelectionFragmentProp({
		defaultValue: KEYS.p,
		getProp: (node) => getBlockType(node as TElement),
	});
	const selectedItem = React.useMemo(
		() => turnIntoItems.find((item) => item.value === (value ?? KEYS.p)) ?? turnIntoItems[0],
		[value]
	);

	return (
		<DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
			<DropdownMenuTrigger asChild>
				<ToolbarButton
					className="min-w-[80px] sm:min-w-[125px]"
					pressed={open}
					tooltip={tooltip}
					isDropdown
				>
					{selectedItem.label}
				</ToolbarButton>
			</DropdownMenuTrigger>

			<DropdownMenuContent
				className="z-[100] ignore-click-outside/toolbar min-w-0 max-h-[60vh] overflow-y-auto dark:bg-neutral-800 dark:border dark:border-neutral-700"
				onCloseAutoFocus={(e) => {
					e.preventDefault();
					editor.tf.focus();
				}}
				align="start"
			>
				<ToolbarMenuGroup
					value={value}
					onValueChange={(type) => {
						setBlockType(editor, type);
					}}
					label="Turn into"
				>
					{turnIntoItems.map(({ icon, label, value: itemValue }) => (
						<DropdownMenuRadioItem
							key={itemValue}
							className="min-w-[180px] pl-2 *:first:[span]:hidden dark:text-white"
							value={itemValue}
						>
							<span className="pointer-events-none absolute right-2 flex size-3.5 items-center justify-center">
								<DropdownMenuItemIndicator>
									<CheckIcon />
								</DropdownMenuItemIndicator>
							</span>
							<span className="text-muted-foreground">{icon}</span>
							{label}
						</DropdownMenuRadioItem>
					))}
				</ToolbarMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
