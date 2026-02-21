"use client";

import { useDraggable, useDropLine } from "@platejs/dnd";
import { BlockSelectionPlugin, useBlockSelected } from "@platejs/selection/react";
import {
	TablePlugin,
	TableProvider,
	useTableCellElement,
	useTableCellElementResizable,
	useTableElement,
	useTableMergeState,
} from "@platejs/table/react";
import { PopoverAnchor } from "@radix-ui/react-popover";
import { cva } from "class-variance-authority";
import {
	ArrowDown,
	ArrowLeft,
	ArrowRight,
	ArrowUp,
	CombineIcon,
	GripVertical,
	SquareSplitHorizontalIcon,
	Trash2Icon,
	XIcon,
} from "lucide-react";
import {
	KEYS,
	PathApi,
	type TElement,
	type TTableCellElement,
	type TTableElement,
	type TTableRowElement,
} from "platejs";
import {
	PlateElement,
	type PlateElementProps,
	useComposedRef,
	useEditorPlugin,
	useEditorRef,
	useEditorSelector,
	useElement,
	useElementSelector,
	useFocusedLast,
	usePluginOption,
	useReadOnly,
	useRemoveNodeButton,
	useSelected,
	withHOC,
} from "platejs/react";
import type * as React from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { blockSelectionVariants } from "./block-selection";
import { ResizeHandle } from "./resize-handle";
import { Toolbar, ToolbarButton, ToolbarGroup } from "./toolbar";

export const TableElement = withHOC(
	TableProvider,
	function TableElement({ children, ...props }: PlateElementProps<TTableElement>) {
		const readOnly = useReadOnly();
		const isSelectionAreaVisible = usePluginOption(BlockSelectionPlugin, "isSelectionAreaVisible");
		const hasControls = !readOnly && !isSelectionAreaVisible;
		const { isSelectingCell, marginLeft, props: tableProps } = useTableElement();

		const isSelectingTable = useBlockSelected(props.element.id as string);

		const content = (
			<PlateElement
				{...props}
				className={cn(
					"overflow-x-auto py-5",
					hasControls && "-ml-2 *:data-[slot=block-selection]:left-2"
				)}
				style={{ paddingLeft: marginLeft }}
			>
				<div className="group/table relative w-fit">
					<table
						className={cn(
							"mr-0 ml-px table h-px w-full table-fixed border-collapse",
							isSelectingCell && "selection:bg-transparent"
						)}
						{...tableProps}
					>
						<tbody className="min-w-full">{children}</tbody>
					</table>

					{isSelectingTable && <div className={blockSelectionVariants()} contentEditable={false} />}
				</div>
			</PlateElement>
		);

		if (readOnly) {
			return content;
		}

		return <TableFloatingToolbar>{content}</TableFloatingToolbar>;
	}
);

function TableFloatingToolbar({ children, ...props }: React.ComponentProps<typeof PopoverContent>) {
	const { tf } = useEditorPlugin(TablePlugin);
	const selected = useSelected();
	const element = useElement<TTableElement>();
	const { props: buttonProps } = useRemoveNodeButton({ element });
	const collapsedInside = useEditorSelector(
		(editor) => selected && editor.api.isCollapsed(),
		[selected]
	);
	const isFocusedLast = useFocusedLast();

	const { canMerge, canSplit } = useTableMergeState();

	return (
		<Popover open={isFocusedLast && (canMerge || canSplit || collapsedInside)} modal={false}>
			<PopoverAnchor asChild>{children}</PopoverAnchor>
			<PopoverContent
				asChild
				onOpenAutoFocus={(e) => e.preventDefault()}
				contentEditable={false}
				{...props}
			>
				<Toolbar
					className="scrollbar-hide flex w-auto max-w-[80vw] flex-row overflow-x-auto rounded-md border bg-popover p-1 shadow-md print:hidden"
					contentEditable={false}
				>
					<ToolbarGroup>
						{canMerge && (
							<ToolbarButton
								onClick={() => tf.table.merge()}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Merge cells"
							>
								<CombineIcon />
							</ToolbarButton>
						)}
						{canSplit && (
							<ToolbarButton
								onClick={() => tf.table.split()}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Split cell"
							>
								<SquareSplitHorizontalIcon />
							</ToolbarButton>
						)}

						{collapsedInside && (
							<ToolbarGroup>
								<ToolbarButton tooltip="Delete table" {...buttonProps}>
									<Trash2Icon />
								</ToolbarButton>
							</ToolbarGroup>
						)}
					</ToolbarGroup>

					{collapsedInside && (
						<ToolbarGroup>
							<ToolbarButton
								onClick={() => {
									tf.insert.tableRow({ before: true });
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Insert row before"
							>
								<ArrowUp />
							</ToolbarButton>
							<ToolbarButton
								onClick={() => {
									tf.insert.tableRow();
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Insert row after"
							>
								<ArrowDown />
							</ToolbarButton>
							<ToolbarButton
								onClick={() => {
									tf.remove.tableRow();
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Delete row"
							>
								<XIcon />
							</ToolbarButton>
						</ToolbarGroup>
					)}

					{collapsedInside && (
						<ToolbarGroup>
							<ToolbarButton
								onClick={() => {
									tf.insert.tableColumn({ before: true });
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Insert column before"
							>
								<ArrowLeft />
							</ToolbarButton>
							<ToolbarButton
								onClick={() => {
									tf.insert.tableColumn();
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Insert column after"
							>
								<ArrowRight />
							</ToolbarButton>
							<ToolbarButton
								onClick={() => {
									tf.remove.tableColumn();
								}}
								onMouseDown={(e) => e.preventDefault()}
								tooltip="Delete column"
							>
								<XIcon />
							</ToolbarButton>
						</ToolbarGroup>
					)}
				</Toolbar>
			</PopoverContent>
		</Popover>
	);
}

export function TableRowElement({ children, ...props }: PlateElementProps<TTableRowElement>) {
	const { element } = props;
	const readOnly = useReadOnly();
	const selected = useSelected();
	const editor = useEditorRef();
	const isSelectionAreaVisible = usePluginOption(BlockSelectionPlugin, "isSelectionAreaVisible");
	const hasControls = !readOnly && !isSelectionAreaVisible;

	const { isDragging, nodeRef, previewRef, handleRef } = useDraggable({
		element,
		type: element.type,
		canDropNode: ({ dragEntry, dropEntry }) =>
			PathApi.equals(PathApi.parent(dragEntry[1]), PathApi.parent(dropEntry[1])),
		onDropHandler: (_, { dragItem }) => {
			const dragElement = (dragItem as { element: TElement }).element;

			if (dragElement) {
				editor.tf.select(dragElement);
			}
		},
	});

	return (
		<PlateElement
			{...props}
			ref={useComposedRef(props.ref, previewRef, nodeRef)}
			as="tr"
			className={cn("group/row", isDragging && "opacity-50")}
			attributes={{
				...props.attributes,
				"data-selected": selected ? "true" : undefined,
			}}
		>
			{hasControls && (
				<td className="w-2 select-none" contentEditable={false}>
					<RowDragHandle dragRef={handleRef} />
					<RowDropLine />
				</td>
			)}

			{children}
		</PlateElement>
	);
}

function RowDragHandle({ dragRef }: { dragRef: React.Ref<any> }) {
	const editor = useEditorRef();
	const element = useElement();

	return (
		<Button
			ref={dragRef}
			variant="outline"
			className={cn(
				"-translate-y-1/2 absolute top-1/2 left-0 z-51 h-6 w-4 p-0 focus-visible:ring-0 focus-visible:ring-offset-0",
				"cursor-grab active:cursor-grabbing",
				'opacity-0 transition-opacity duration-100 group-hover/row:opacity-100 group-has-data-[resizing="true"]/row:opacity-0'
			)}
			onClick={() => {
				editor.tf.select(element);
			}}
		>
			<GripVertical className="text-muted-foreground" />
		</Button>
	);
}

function RowDropLine() {
	const { dropLine } = useDropLine();

	if (!dropLine) return null;

	return (
		<div
			className={cn(
				"absolute inset-x-0 left-2 z-50 h-0.5 bg-brand/50",
				dropLine === "top" ? "-top-px" : "-bottom-px"
			)}
		/>
	);
}

export function TableCellElement({
	isHeader,
	...props
}: PlateElementProps<TTableCellElement> & {
	isHeader?: boolean;
}) {
	const { api } = useEditorPlugin(TablePlugin);
	const readOnly = useReadOnly();
	const element = props.element;

	const tableId = useElementSelector(([node]) => node.id as string, [], {
		key: KEYS.table,
	});
	const rowId = useElementSelector(([node]) => node.id as string, [], {
		key: KEYS.tr,
	});
	const isSelectingTable = useBlockSelected(tableId);
	const isSelectingRow = useBlockSelected(rowId) || isSelectingTable;
	const isSelectionAreaVisible = usePluginOption(BlockSelectionPlugin, "isSelectionAreaVisible");

	const { borders, colIndex, colSpan, minHeight, rowIndex, selected, width } =
		useTableCellElement();

	const { bottomProps, hiddenLeft, leftProps, rightProps } = useTableCellElementResizable({
		colIndex,
		colSpan,
		rowIndex,
	});

	return (
		<PlateElement
			{...props}
			as={isHeader ? "th" : "td"}
			className={cn(
				"h-full overflow-visible border-none bg-background p-0",
				element.background ? "bg-(--cellBackground)" : "bg-background",
				isHeader && "text-left *:m-0",
				"before:size-full",
				selected && "before:z-10 before:bg-brand/5",
				"before:absolute before:box-border before:select-none before:content-['']",
				borders.bottom?.size && "before:border-b before:border-b-border",
				borders.right?.size && "before:border-r before:border-r-border",
				borders.left?.size && "before:border-l before:border-l-border",
				borders.top?.size && "before:border-t before:border-t-border"
			)}
			style={
				{
					"--cellBackground": element.background,
					minWidth: width || 48,
				} as React.CSSProperties
			}
			attributes={{
				...props.attributes,
				colSpan: api.table.getColSpan(element),
				rowSpan: api.table.getRowSpan(element),
			}}
		>
			<div className="relative z-20 box-border h-full px-3 py-2" style={{ minHeight }}>
				{props.children}
			</div>

			{!isSelectionAreaVisible && (
				<div
					className="group absolute top-0 size-full select-none"
					contentEditable={false}
					suppressContentEditableWarning={true}
				>
					{!readOnly && (
						<>
							<ResizeHandle
								{...rightProps}
								className="-top-2 -right-1 h-[calc(100%_+_8px)] w-2"
								data-col={colIndex}
							/>
							<ResizeHandle {...bottomProps} className="-bottom-1 h-2" />
							{!hiddenLeft && (
								<ResizeHandle
									{...leftProps}
									className="-left-1 top-0 w-2"
									data-resizer-left={colIndex === 0 ? "true" : undefined}
								/>
							)}

							<div
								className={cn(
									"absolute top-0 z-30 hidden h-full w-1 bg-ring",
									"right-[-1.5px]",
									columnResizeVariants({ colIndex: colIndex as any })
								)}
							/>
							{colIndex === 0 && (
								<div
									className={cn(
										"absolute top-0 z-30 h-full w-1 bg-ring",
										"left-[-1.5px]",
										'fade-in hidden animate-in group-has-[[data-resizer-left]:hover]/table:block group-has-[[data-resizer-left][data-resizing="true"]]/table:block'
									)}
								/>
							)}
						</>
					)}
				</div>
			)}

			{isSelectingRow && <div className={blockSelectionVariants()} contentEditable={false} />}
		</PlateElement>
	);
}

export function TableCellHeaderElement(props: React.ComponentProps<typeof TableCellElement>) {
	return <TableCellElement {...props} isHeader />;
}

const columnResizeVariants = cva("fade-in hidden animate-in", {
	variants: {
		colIndex: {
			0: 'group-has-[[data-col="0"]:hover]/table:block group-has-[[data-col="0"][data-resizing="true"]]/table:block',
			1: 'group-has-[[data-col="1"]:hover]/table:block group-has-[[data-col="1"][data-resizing="true"]]/table:block',
			2: 'group-has-[[data-col="2"]:hover]/table:block group-has-[[data-col="2"][data-resizing="true"]]/table:block',
			3: 'group-has-[[data-col="3"]:hover]/table:block group-has-[[data-col="3"][data-resizing="true"]]/table:block',
			4: 'group-has-[[data-col="4"]:hover]/table:block group-has-[[data-col="4"][data-resizing="true"]]/table:block',
			5: 'group-has-[[data-col="5"]:hover]/table:block group-has-[[data-col="5"][data-resizing="true"]]/table:block',
			6: 'group-has-[[data-col="6"]:hover]/table:block group-has-[[data-col="6"][data-resizing="true"]]/table:block',
			7: 'group-has-[[data-col="7"]:hover]/table:block group-has-[[data-col="7"][data-resizing="true"]]/table:block',
			8: 'group-has-[[data-col="8"]:hover]/table:block group-has-[[data-col="8"][data-resizing="true"]]/table:block',
			9: 'group-has-[[data-col="9"]:hover]/table:block group-has-[[data-col="9"][data-resizing="true"]]/table:block',
			10: 'group-has-[[data-col="10"]:hover]/table:block group-has-[[data-col="10"][data-resizing="true"]]/table:block',
		},
	},
});
