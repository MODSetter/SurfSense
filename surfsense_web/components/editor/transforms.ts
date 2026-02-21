"use client";

import { insertCallout } from "@platejs/callout";
import { insertCodeBlock, toggleCodeBlock } from "@platejs/code-block";
import { triggerFloatingLink } from "@platejs/link/react";
import { insertInlineEquation } from "@platejs/math";
import { TablePlugin } from "@platejs/table/react";
import { KEYS, type NodeEntry, type Path, PathApi, type TElement } from "platejs";
import type { PlateEditor } from "platejs/react";

const insertList = (editor: PlateEditor, type: string) => {
	editor.tf.insertNodes(
		editor.api.create.block({
			indent: 1,
			listStyleType: type,
		}),
		{ select: true }
	);
};

const insertBlockMap: Record<string, (editor: PlateEditor, type: string) => void> = {
	[KEYS.listTodo]: insertList,
	[KEYS.ol]: insertList,
	[KEYS.ul]: insertList,
	[KEYS.codeBlock]: (editor) => insertCodeBlock(editor, { select: true }),
	[KEYS.table]: (editor) => editor.getTransforms(TablePlugin).insert.table({}, { select: true }),
	[KEYS.callout]: (editor) => insertCallout(editor, { select: true }),
	[KEYS.toggle]: (editor) => {
		editor.tf.insertNodes(editor.api.create.block({ type: KEYS.toggle }), { select: true });
	},
};

const insertInlineMap: Record<string, (editor: PlateEditor, type: string) => void> = {
	[KEYS.link]: (editor) => triggerFloatingLink(editor, { focused: true }),
	[KEYS.equation]: (editor) => insertInlineEquation(editor),
};

type InsertBlockOptions = {
	upsert?: boolean;
};

export const insertBlock = (
	editor: PlateEditor,
	type: string,
	options: InsertBlockOptions = {}
) => {
	const { upsert = false } = options;

	editor.tf.withoutNormalizing(() => {
		const block = editor.api.block();

		if (!block) return;

		const [currentNode, path] = block;
		const isCurrentBlockEmpty = editor.api.isEmpty(currentNode);
		const currentBlockType = getBlockType(currentNode);

		const isSameBlockType = type === currentBlockType;

		if (upsert && isCurrentBlockEmpty && isSameBlockType) {
			return;
		}

		if (type in insertBlockMap) {
			insertBlockMap[type](editor, type);
		} else {
			editor.tf.insertNodes(editor.api.create.block({ type }), {
				at: PathApi.next(path),
				select: true,
			});
		}

		if (!isSameBlockType) {
			editor.tf.removeNodes({ previousEmptyBlock: true });
		}
	});
};

export const insertInlineElement = (editor: PlateEditor, type: string) => {
	if (insertInlineMap[type]) {
		insertInlineMap[type](editor, type);
	}
};

const setList = (editor: PlateEditor, type: string, entry: NodeEntry<TElement>) => {
	editor.tf.setNodes(
		editor.api.create.block({
			indent: 1,
			listStyleType: type,
		}),
		{
			at: entry[1],
		}
	);
};

const setBlockMap: Record<
	string,
	(editor: PlateEditor, type: string, entry: NodeEntry<TElement>) => void
> = {
	[KEYS.listTodo]: setList,
	[KEYS.ol]: setList,
	[KEYS.ul]: setList,
	[KEYS.codeBlock]: (editor) => toggleCodeBlock(editor),
	[KEYS.callout]: (editor, _type, entry) => {
		editor.tf.setNodes({ type: KEYS.callout }, { at: entry[1] });
	},
	[KEYS.toggle]: (editor, _type, entry) => {
		editor.tf.setNodes({ type: KEYS.toggle }, { at: entry[1] });
	},
};

export const setBlockType = (editor: PlateEditor, type: string, { at }: { at?: Path } = {}) => {
	editor.tf.withoutNormalizing(() => {
		const setEntry = (entry: NodeEntry<TElement>) => {
			const [node, path] = entry;

			if (node[KEYS.listType]) {
				editor.tf.unsetNodes([KEYS.listType, "indent"], { at: path });
			}
			if (type in setBlockMap) {
				return setBlockMap[type](editor, type, entry);
			}
			if (node.type !== type) {
				editor.tf.setNodes({ type }, { at: path });
			}
		};

		if (at) {
			const entry = editor.api.node<TElement>(at);

			if (entry) {
				setEntry(entry);

				return;
			}
		}

		const entries = editor.api.blocks({ mode: "lowest" });

		entries.forEach((entry) => {
			setEntry(entry);
		});
	});
};

export const getBlockType = (block: TElement) => {
	if (block[KEYS.listType]) {
		if (block[KEYS.listType] === KEYS.ol) {
			return KEYS.ol;
		}
		if (block[KEYS.listType] === KEYS.listTodo) {
			return KEYS.listTodo;
		}
		return KEYS.ul;
	}

	return block.type;
};
