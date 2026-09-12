"use client";

import katex from "katex";
import "katex/dist/katex.min.css";
import { useLayoutEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/utils";
import { parseStudyText } from "./parse-text";

const KATEX_OPTIONS = {
	output: "htmlAndMathml",
	throwOnError: false,
	trust: false,
	strict: "error",
	maxExpand: 1_000,
	maxSize: 10,
} as const;

function Formula({ value, display }: { value: string; display: boolean }) {
	const containerRef = useRef<HTMLSpanElement>(null);

	useLayoutEffect(() => {
		if (containerRef.current) {
			katex.render(value, containerRef.current, {
				...KATEX_OPTIONS,
				displayMode: display,
			});
		}
	}, [display, value]);

	return (
		<span
			ref={containerRef}
			className={
				display
					? "my-2 block max-w-full overflow-x-auto overflow-y-hidden py-1"
					: "inline-block max-w-full align-middle"
			}
		/>
	);
}

export function StudyText({ content, className }: { content: string; className?: string }) {
	const segments = useMemo(() => {
		const parsed = parseStudyText(content);
		if (!parsed) throw new Error("Study text violated the verified contract");
		return parsed;
	}, [content]);

	return (
		<span className={cn("whitespace-pre-wrap", className)}>
			{segments.map((segment) =>
				segment.type === "text" ? (
					<span key={segment.offset}>{segment.value}</span>
				) : (
					<Formula key={segment.offset} value={segment.value} display={segment.display} />
				)
			)}
		</span>
	);
}
