"use client";

import { Maximize2 } from "lucide-react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { ArtifactRendererProps } from "@/features/artifacts/model/renderer";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";

interface AccessibleNode {
	id: string;
	label: string;
	children: AccessibleNode[];
}

interface TransformedNode {
	content?: unknown;
	children?: unknown;
}

const MAX_SOURCE_LENGTH = 50_000;
const MAX_ACCESSIBLE_NODES = 1_000;
const MAX_ACCESSIBLE_DEPTH = 32;
const transformer = new Transformer([]);

transformer.md.set({ html: false, linkify: false });
transformer.md.renderer.rules.link_open = () => "";
transformer.md.renderer.rules.link_close = () => "";
transformer.md.renderer.rules.image = (tokens: Array<{ content: string }>, index: number) =>
	transformer.md.utils.escapeHtml(tokens[index]?.content ?? "");

function textContent(html: string): string {
	const document = new DOMParser().parseFromString(html, "text/html");
	return document.body.textContent?.trim() ?? "";
}

function toAccessibleTree(root: unknown): AccessibleNode {
	let nodeCount = 0;

	function visit(value: unknown, depth: number, id: string): AccessibleNode {
		if (
			depth > MAX_ACCESSIBLE_DEPTH ||
			++nodeCount > MAX_ACCESSIBLE_NODES ||
			typeof value !== "object" ||
			value === null
		) {
			throw new Error("Invalid mind-map hierarchy");
		}

		const node = value as TransformedNode;
		if (typeof node.content !== "string") throw new Error("Invalid mind-map node");
		const label = textContent(node.content);
		if (!label) throw new Error("Mind-map nodes need labels");

		const children = node.children ?? [];
		if (!Array.isArray(children)) throw new Error("Invalid mind-map children");
		return {
			id,
			label,
			children: children.map((child, index) => visit(child, depth + 1, `${id}.${index}`)),
		};
	}

	return visit(root, 0, "root");
}

function ScreenReaderTree({ node }: { node: AccessibleNode }) {
	return (
		<li>
			<span>{node.label}</span>
			{node.children.length > 0 ? (
				<ul>
					{node.children.map((child) => (
						<ScreenReaderTree key={child.id} node={child} />
					))}
				</ul>
			) : null}
		</li>
	);
}

export default function MindMapViewer({ manifest, zoomControlsContainer }: ArtifactRendererProps) {
	const markdown = manifest.markdown_representation;
	const svgRef = useRef<SVGSVGElement>(null);
	const markmapRef = useRef<Markmap | null>(null);
	const reducedMotion = useReducedMotion() ?? false;
	const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
	const [accessibleRoot, setAccessibleRoot] = useState<AccessibleNode | null>(null);

	useEffect(() => {
		const svg = svgRef.current;
		if (!svg) return;
		const markmap = Markmap.create(svg, {
			initialExpandLevel: -1,
			pan: true,
			zoom: true,
		});
		markmapRef.current = markmap;

		return () => {
			markmapRef.current = null;
			markmap.destroy();
		};
	}, []);

	useEffect(() => {
		markmapRef.current?.setOptions({ duration: reducedMotion ? 0 : 500 });
	}, [reducedMotion]);

	useEffect(() => {
		let cancelled = false;
		setStatus("loading");
		setAccessibleRoot(null);

		async function render() {
			try {
				const markmap = markmapRef.current;
				if (!markdown.trim() || markdown.length > MAX_SOURCE_LENGTH || !markmap) {
					throw new Error("Invalid mind-map source");
				}

				const { root } = transformer.transform(markdown);
				const tree = toAccessibleTree(root);
				if (tree.children.length === 0) throw new Error("Mind map needs at least one child");

				await markmap.setData(root);
				if (cancelled) return;
				await markmap.fit();
				if (cancelled) return;
				setAccessibleRoot(tree);
				setStatus("ready");
			} catch {
				if (!cancelled) setStatus("error");
			}
		}

		void render();
		return () => {
			cancelled = true;
		};
	}, [markdown]);

	if (status === "error") {
		return (
			<UnviewableFile message="This mind map can't be displayed. Download the PNG to open it." />
		);
	}

	const fitControl =
		status === "ready" ? (
			<Button
				type="button"
				variant="ghost"
				size="icon"
				onClick={() => void markmapRef.current?.fit()}
				className="size-6 shrink-0 rounded-full text-muted-foreground"
			>
				<Maximize2 className="size-4" />
				<span className="sr-only">Fit mind map</span>
			</Button>
		) : null;

	return (
		<div data-vaul-no-drag="" className="relative h-full min-h-0 overflow-hidden bg-white">
			{fitControl && zoomControlsContainer ? createPortal(fitControl, zoomControlsContainer) : null}
			<svg
				ref={svgRef}
				className="absolute inset-0 h-full w-full touch-none"
				aria-hidden="true"
				focusable="false"
			/>
			{status === "loading" ? (
				<div className="absolute inset-0 flex items-center justify-center" aria-busy="true">
					<Spinner size="lg" />
				</div>
			) : null}
			{accessibleRoot ? (
				<div className="sr-only">
					<ul aria-label="Mind map">
						<ScreenReaderTree node={accessibleRoot} />
					</ul>
				</div>
			) : null}
		</div>
	);
}
