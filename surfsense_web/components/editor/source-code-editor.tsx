"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";
import { Spinner } from "@/components/ui/spinner";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
	ssr: false,
});

interface SourceCodeEditorProps {
	value: string;
	onChange: (next: string) => void;
	path?: string;
	language?: string;
	readOnly?: boolean;
	fontSize?: number;
	onSave?: () => Promise<void> | void;
	saveMode?: "manual" | "auto" | "both";
	autoSaveDelayMs?: number;
}

export function SourceCodeEditor({
	value,
	onChange,
	path,
	language = "plaintext",
	readOnly = false,
	fontSize = 12,
	onSave,
	saveMode = "manual",
	autoSaveDelayMs = 800,
}: SourceCodeEditorProps) {
	const { resolvedTheme } = useTheme();
	const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const onSaveRef = useRef(onSave);
	const skipNextAutoSaveRef = useRef(true);

	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	useEffect(() => {
		skipNextAutoSaveRef.current = true;
	}, [path]);

	useEffect(() => {
		if (readOnly || !onSaveRef.current) return;
		if (saveMode !== "auto" && saveMode !== "both") return;

		if (skipNextAutoSaveRef.current) {
			skipNextAutoSaveRef.current = false;
			return;
		}

		if (saveTimerRef.current) {
			clearTimeout(saveTimerRef.current);
		}

		saveTimerRef.current = setTimeout(() => {
			void onSaveRef.current?.();
			saveTimerRef.current = null;
		}, autoSaveDelayMs);

		return () => {
			if (saveTimerRef.current) {
				clearTimeout(saveTimerRef.current);
				saveTimerRef.current = null;
			}
		};
	}, [autoSaveDelayMs, readOnly, saveMode, value]);

	const isManualSaveEnabled = !!onSave && !readOnly && (saveMode === "manual" || saveMode === "both");

	return (
		<div className="h-full w-full overflow-hidden bg-sidebar [&_.monaco-scrollable-element_.scrollbar_.slider]:rounded-full [&_.monaco-scrollable-element_.scrollbar_.slider]:bg-foreground/25 [&_.monaco-scrollable-element_.scrollbar_.slider:hover]:bg-foreground/40">
			<MonacoEditor
				path={path}
				language={language}
				value={value}
				theme={resolvedTheme === "dark" ? "vs-dark" : "vs"}
				onChange={(next) => onChange(next ?? "")}
				loading={
					<div className="flex h-full w-full items-center justify-center">
						<Spinner size="sm" className="text-muted-foreground" />
					</div>
				}
				onMount={(editor, monaco) => {
					if (!isManualSaveEnabled) return;
					editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
						void onSaveRef.current?.();
					});
				}}
				options={{
					automaticLayout: true,
					minimap: { enabled: false },
					lineNumbers: "on",
					lineNumbersMinChars: 3,
					lineDecorationsWidth: 12,
					glyphMargin: false,
					folding: true,
					overviewRulerLanes: 0,
					hideCursorInOverviewRuler: true,
					scrollBeyondLastLine: false,
					renderLineHighlight: "none",
					selectionHighlight: false,
					occurrencesHighlight: "off",
					quickSuggestions: false,
					suggestOnTriggerCharacters: false,
					acceptSuggestionOnEnter: "off",
					parameterHints: { enabled: false },
					wordBasedSuggestions: "off",
					wordWrap: "off",
					scrollbar: {
						vertical: "auto",
						horizontal: "auto",
						verticalScrollbarSize: 8,
						horizontalScrollbarSize: 8,
						alwaysConsumeMouseWheel: false,
					},
					tabSize: 2,
					insertSpaces: true,
					fontSize,
					fontFamily:
						"ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace",
					renderWhitespace: "selection",
					smoothScrolling: true,
					readOnly,
				}}
			/>
		</div>
	);
}
