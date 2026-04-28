"use client";

import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";
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
}

export function SourceCodeEditor({
	value,
	onChange,
	path,
	language = "plaintext",
	readOnly = false,
	fontSize = 12,
	onSave,
}: SourceCodeEditorProps) {
	const { resolvedTheme } = useTheme();
	const onSaveRef = useRef(onSave);
	const monacoRef = useRef<any>(null);
	const normalizedModelPath = (() => {
		const raw = (path || "local-file.txt").trim();
		const withLeadingSlash = raw.startsWith("/") ? raw : `/${raw}`;
		// Monaco model paths should be stable and POSIX-like across platforms.
		return withLeadingSlash.replace(/\\/g, "/").replace(/\/{2,}/g, "/");
	})();

	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	const resolveCssColorToHex = (cssColorValue: string): string | null => {
		if (typeof document === "undefined") return null;
		const probe = document.createElement("div");
		probe.style.color = cssColorValue;
		probe.style.position = "absolute";
		probe.style.pointerEvents = "none";
		probe.style.opacity = "0";
		document.body.appendChild(probe);
		const computedColor = getComputedStyle(probe).color;
		probe.remove();
		const match = computedColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
		if (!match) return null;
		const toHex = (value: string) => Number(value).toString(16).padStart(2, "0");
		return `#${toHex(match[1])}${toHex(match[2])}${toHex(match[3])}`;
	};

	const applySidebarTheme = (monaco: any) => {
		const isDark = resolvedTheme === "dark";
		const themeName = isDark ? "surfsense-dark" : "surfsense-light";
		const fallbackBg = isDark ? "#1e1e1e" : "#ffffff";
		const sidebarBgHex = resolveCssColorToHex("var(--sidebar)") ?? fallbackBg;
		monaco.editor.defineTheme(themeName, {
			base: isDark ? "vs-dark" : "vs",
			inherit: true,
			rules: [],
			colors: {
				"editor.background": sidebarBgHex,
				"editorGutter.background": sidebarBgHex,
				"minimap.background": sidebarBgHex,
				"editorLineNumber.background": sidebarBgHex,
				"editor.lineHighlightBackground": "#00000000",
			},
		});
		monaco.editor.setTheme(themeName);
	};

	useEffect(() => {
		if (!monacoRef.current) return;
		applySidebarTheme(monacoRef.current);
	}, [resolvedTheme]);

	const isManualSaveEnabled = !!onSave && !readOnly;

	return (
		<div className="h-full w-full overflow-hidden bg-sidebar [&_.monaco-editor]:!bg-sidebar [&_.monaco-editor_.margin]:!bg-sidebar [&_.monaco-editor_.monaco-editor-background]:!bg-sidebar [&_.monaco-editor-background]:!bg-sidebar [&_.monaco-scrollable-element_.scrollbar_.slider]:rounded-full [&_.monaco-scrollable-element_.scrollbar_.slider]:bg-foreground/25 [&_.monaco-scrollable-element_.scrollbar_.slider:hover]:bg-foreground/40">
			<MonacoEditor
				path={normalizedModelPath}
				language={language}
				value={value}
				theme={resolvedTheme === "dark" ? "surfsense-dark" : "surfsense-light"}
				onChange={(next) => onChange(next ?? "")}
				loading={
					<div className="flex h-full w-full items-center justify-center">
						<Spinner size="md" className="text-muted-foreground" />
					</div>
				}
				beforeMount={(monaco) => {
					monacoRef.current = monaco;
					applySidebarTheme(monaco);
				}}
				onMount={(editor, monaco) => {
					monacoRef.current = monaco;
					applySidebarTheme(monaco);
					if (!isManualSaveEnabled) return;
					editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
						void onSaveRef.current?.();
					});
				}}
				options={{
					automaticLayout: true,
					minimap: { enabled: false },
					lineNumbers: "on",
					lineNumbersMinChars: 4,
					lineDecorationsWidth: 20,
					glyphMargin: false,
					folding: false,
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
					renderWhitespace: "none",
					renderValidationDecorations: "off",
					colorDecorators: false,
					codeLens: false,
					hover: { enabled: false },
					stickyScroll: { enabled: false },
					unicodeHighlight: {
						ambiguousCharacters: false,
						invisibleCharacters: false,
						nonBasicASCII: false,
					},
					smoothScrolling: true,
					readOnly,
				}}
			/>
		</div>
	);
}
