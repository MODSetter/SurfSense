"use client";

import { DndPlugin, useDraggable, useDropLine } from "@platejs/dnd";
import { expandListItemsWithChildren } from "@platejs/list";
import { BlockSelectionPlugin } from "@platejs/selection/react";
import { GripVertical } from "lucide-react";
import { getPluginByType, isType, KEYS, type TElement } from "platejs";
import {
	MemoizedChildren,
	type PlateEditor,
	type PlateElementProps,
	type RenderNodeWrapper,
	useEditorRef,
	useElement,
	usePluginOption,
	useSelected,
} from "platejs/react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const UNDRAGGABLE_KEYS = [KEYS.column, KEYS.tr, KEYS.td];

export const BlockDraggable: RenderNodeWrapper = (props) => {
	const { editor, element, path } = props;

	const enabled = React.useMemo(() => {
		if (editor.dom.readOnly) return false;

		if (path.length === 1 && !isType(editor, element, UNDRAGGABLE_KEYS)) {
			return true;
		}
		if (path.length === 3 && !isType(editor, element, UNDRAGGABLE_KEYS)) {
			const block = editor.api.some({
				at: path,
				match: {
					type: editor.getType(KEYS.column),
				},
			});

			if (block) {
				return true;
			}
		}
		if (path.length === 4 && !isType(editor, element, UNDRAGGABLE_KEYS)) {
			const block = editor.api.some({
				at: path,
				match: {
					type: editor.getType(KEYS.table),
				},
			});

			if (block) {
				return true;
			}
		}

		return false;
	}, [editor, element, path]);

	if (!enabled) return;

	return (props) => <Draggable {...props} />;
};

function Draggable(props: PlateElementProps) {
	const { children, editor, element, path } = props;
	const blockSelectionApi = editor.getApi(BlockSelectionPlugin).blockSelection;

	const { isAboutToDrag, isDragging, nodeRef, previewRef, handleRef } = useDraggable({
		element,
		onDropHandler: (_, { dragItem }) => {
			const id = (dragItem as { id: string[] | string }).id;

			if (blockSelectionApi) {
				blockSelectionApi.add(id);
			}
			resetPreview();
		},
	});

	const isInColumn = path.length === 3;
	const isInTable = path.length === 4;

	const [previewTop, setPreviewTop] = React.useState(0);

	const resetPreview = () => {
		if (previewRef.current) {
			previewRef.current.replaceChildren();
			previewRef.current?.classList.add("hidden");
		}
	};

	// clear up virtual multiple preview when drag end
	React.useEffect(() => {
		if (!isDragging) {
			resetPreview();
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [isDragging]);

	React.useEffect(() => {
		if (isAboutToDrag) {
			previewRef.current?.classList.remove("opacity-0");
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [isAboutToDrag]);

	const [dragButtonTop, setDragButtonTop] = React.useState(0);

	return (
		<div
			className={cn(
				"relative",
				isDragging && "opacity-50",
				getPluginByType(editor, element.type)?.node.isContainer ? "group/container" : "group"
			)}
			onMouseEnter={() => {
				if (isDragging) return;
				setDragButtonTop(calcDragButtonTop(editor, element));
			}}
		>
			{!isInTable && (
				<Gutter>
					<div className={cn("slate-blockToolbarWrapper", "flex h-[1.5em]", isInColumn && "h-4")}>
						<div
							className={cn(
								"slate-blockToolbar relative w-4.5",
								"pointer-events-auto mr-1 flex items-center",
								isInColumn && "mr-1.5"
							)}
						>
							<Button
								ref={handleRef}
								variant="ghost"
								className="-left-0 absolute h-6 w-full p-0"
								style={{ top: `${dragButtonTop + 3}px` }}
								data-plate-prevent-deselect
							>
								<DragHandle
									isDragging={isDragging}
									previewRef={previewRef}
									resetPreview={resetPreview}
									setPreviewTop={setPreviewTop}
								/>
							</Button>
						</div>
					</div>
				</Gutter>
			)}

			<div
				ref={previewRef}
				className={cn("-left-0 absolute hidden w-full")}
				style={{ top: `${-previewTop}px` }}
				contentEditable={false}
			/>

			<div
				ref={nodeRef}
				className="slate-blockWrapper flow-root"
				onContextMenu={(event) =>
					editor.getApi(BlockSelectionPlugin).blockSelection.addOnContextMenu({ element, event })
				}
			>
				<MemoizedChildren>{children}</MemoizedChildren>
				<DropLine />
			</div>
		</div>
	);
}

function Gutter({ children, className, ...props }: React.ComponentProps<"div">) {
	const editor = useEditorRef();
	const element = useElement();
	const isSelectionAreaVisible = usePluginOption(BlockSelectionPlugin, "isSelectionAreaVisible");
	const selected = useSelected();

	return (
		<div
			{...props}
			className={cn(
				"slate-gutterLeft",
				"-translate-x-full absolute top-0 z-50 flex h-full cursor-text hover:opacity-100 sm:opacity-0",
				getPluginByType(editor, element.type)?.node.isContainer
					? "group-hover/container:opacity-100"
					: "group-hover:opacity-100",
				isSelectionAreaVisible && "hidden",
				!selected && "opacity-0",
				className
			)}
			contentEditable={false}
		>
			{children}
		</div>
	);
}

const DragHandle = React.memo(function DragHandle({
	isDragging,
	previewRef,
	resetPreview,
	setPreviewTop,
}: {
	isDragging: boolean;
	previewRef: React.RefObject<HTMLDivElement | null>;
	resetPreview: () => void;
	setPreviewTop: (top: number) => void;
}) {
	const editor = useEditorRef();
	const element = useElement();

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<div
					className="flex size-full items-center justify-center"
					onClick={(e) => {
						e.preventDefault();
						editor.getApi(BlockSelectionPlugin).blockSelection.focus();
					}}
					onMouseDown={(e) => {
						resetPreview();

						if ((e.button !== 0 && e.button !== 2) || e.shiftKey) return;

						const blockSelection = editor
							.getApi(BlockSelectionPlugin)
							.blockSelection.getNodes({ sort: true });

						let selectionNodes =
							blockSelection.length > 0 ? blockSelection : editor.api.blocks({ mode: "highest" });

						// If current block is not in selection, use it as the starting point
						if (!selectionNodes.some(([node]) => node.id === element.id)) {
							selectionNodes = [[element, editor.api.findPath(element)!]];
						}

						// Process selection nodes to include list children
						const blocks = expandListItemsWithChildren(editor, selectionNodes).map(
							([node]) => node
						);

						if (blockSelection.length === 0) {
							editor.tf.blur();
							editor.tf.collapse();
						}

						const elements = createDragPreviewElements(editor, blocks);
						previewRef.current?.append(...elements);
						previewRef.current?.classList.remove("hidden");
						previewRef.current?.classList.add("opacity-0");
						editor.setOption(DndPlugin, "multiplePreviewRef", previewRef);

						editor
							.getApi(BlockSelectionPlugin)
							.blockSelection.set(blocks.map((block) => block.id as string));
					}}
					onMouseEnter={() => {
						if (isDragging) return;

						const blockSelection = editor
							.getApi(BlockSelectionPlugin)
							.blockSelection.getNodes({ sort: true });

						let selectedBlocks =
							blockSelection.length > 0 ? blockSelection : editor.api.blocks({ mode: "highest" });

						// If current block is not in selection, use it as the starting point
						if (!selectedBlocks.some(([node]) => node.id === element.id)) {
							selectedBlocks = [[element, editor.api.findPath(element)!]];
						}

						// Process selection to include list children
						const processedBlocks = expandListItemsWithChildren(editor, selectedBlocks);

						const ids = processedBlocks.map((block) => block[0].id as string);

						if (ids.length > 1 && ids.includes(element.id as string)) {
							const previewTop = calculatePreviewTop(editor, {
								blocks: processedBlocks.map((block) => block[0]),
								element,
							});
							setPreviewTop(previewTop);
						} else {
							setPreviewTop(0);
						}
					}}
					onMouseUp={() => {
						resetPreview();
					}}
					data-plate-prevent-deselect
					role="button"
				>
					<GripVertical className="text-muted-foreground" />
				</div>
			</TooltipTrigger>
		</Tooltip>
	);
});

const DropLine = React.memo(function DropLine({
	className,
	...props
}: React.ComponentProps<"div">) {
	const { dropLine } = useDropLine();

	if (!dropLine) return null;

	return (
		<div
			{...props}
			className={cn(
				"slate-dropLine",
				"absolute inset-x-0 h-0.5 opacity-100 transition-opacity",
				"bg-brand/50",
				dropLine === "top" && "-top-px",
				dropLine === "bottom" && "-bottom-px",
				className
			)}
		/>
	);
});

const createDragPreviewElements = (editor: PlateEditor, blocks: TElement[]): HTMLElement[] => {
	const elements: HTMLElement[] = [];
	const ids: string[] = [];

	/**
	 * Remove data attributes from the element to avoid recognized as slate
	 * elements incorrectly.
	 */
	const removeDataAttributes = (element: HTMLElement) => {
		Array.from(element.attributes).forEach((attr) => {
			if (attr.name.startsWith("data-slate") || attr.name.startsWith("data-block-id")) {
				element.removeAttribute(attr.name);
			}
		});

		Array.from(element.children).forEach((child) => {
			removeDataAttributes(child as HTMLElement);
		});
	};

	const resolveElement = (node: TElement, index: number) => {
		const domNode = editor.api.toDOMNode(node)!;
		const newDomNode = domNode.cloneNode(true) as HTMLElement;

		// Apply visual compensation for horizontal scroll
		const applyScrollCompensation = (original: Element, cloned: HTMLElement) => {
			const scrollLeft = original.scrollLeft;

			if (scrollLeft > 0) {
				// Create a wrapper to handle the scroll offset
				const scrollWrapper = document.createElement("div");
				scrollWrapper.style.overflow = "hidden";
				scrollWrapper.style.width = `${original.clientWidth}px`;

				// Create inner container with the full content
				const innerContainer = document.createElement("div");
				innerContainer.style.transform = `translateX(-${scrollLeft}px)`;
				innerContainer.style.width = `${original.scrollWidth}px`;

				// Move all children to the inner container
				while (cloned.firstChild) {
					innerContainer.append(cloned.firstChild);
				}

				// Apply the original element's styles to maintain appearance
				const originalStyles = window.getComputedStyle(original);
				cloned.style.padding = "0";
				innerContainer.style.padding = originalStyles.padding;

				scrollWrapper.append(innerContainer);
				cloned.append(scrollWrapper);
			}
		};

		applyScrollCompensation(domNode, newDomNode);

		ids.push(node.id as string);
		const wrapper = document.createElement("div");
		wrapper.append(newDomNode);
		wrapper.style.display = "flow-root";

		const lastDomNode = blocks[index - 1];

		if (lastDomNode) {
			const lastDomNodeRect = editor.api
				.toDOMNode(lastDomNode)!
				.parentElement!.getBoundingClientRect();

			const domNodeRect = domNode.parentElement!.getBoundingClientRect();

			const distance = domNodeRect.top - lastDomNodeRect.bottom;

			// Check if the two elements are adjacent (touching each other)
			if (distance > 15) {
				wrapper.style.marginTop = `${distance}px`;
			}
		}

		removeDataAttributes(newDomNode);
		elements.push(wrapper);
	};

	blocks.forEach((node, index) => {
		resolveElement(node, index);
	});

	editor.setOption(DndPlugin, "draggingId", ids);

	return elements;
};

const calculatePreviewTop = (
	editor: PlateEditor,
	{
		blocks,
		element,
	}: {
		blocks: TElement[];
		element: TElement;
	}
): number => {
	const child = editor.api.toDOMNode(element)!;
	const editable = editor.api.toDOMNode(editor)!;
	const firstSelectedChild = blocks[0];

	const firstDomNode = editor.api.toDOMNode(firstSelectedChild)!;
	// Get editor's top padding
	const editorPaddingTop = Number(window.getComputedStyle(editable).paddingTop.replace("px", ""));

	// Calculate distance from first selected node to editor top
	const firstNodeToEditorDistance =
		firstDomNode.getBoundingClientRect().top -
		editable.getBoundingClientRect().top -
		editorPaddingTop;

	// Get margin top of first selected node
	const firstMarginTopString = window.getComputedStyle(firstDomNode).marginTop;
	const marginTop = Number(firstMarginTopString.replace("px", ""));

	// Calculate distance from current node to editor top
	const currentToEditorDistance =
		child.getBoundingClientRect().top - editable.getBoundingClientRect().top - editorPaddingTop;

	const currentMarginTopString = window.getComputedStyle(child).marginTop;
	const currentMarginTop = Number(currentMarginTopString.replace("px", ""));

	const previewElementsTopDistance =
		currentToEditorDistance - firstNodeToEditorDistance + marginTop - currentMarginTop;

	return previewElementsTopDistance;
};

const calcDragButtonTop = (editor: PlateEditor, element: TElement): number => {
	const child = editor.api.toDOMNode(element)!;

	const currentMarginTopString = window.getComputedStyle(child).marginTop;
	const currentMarginTop = Number(currentMarginTopString.replace("px", ""));

	return currentMarginTop;
};
