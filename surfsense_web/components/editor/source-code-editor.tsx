"use client";

import dynamic from "next/dynamic";
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
}

export function SourceCodeEditor({
	value,
	onChange,
	path,
	language = "plaintext",
	readOnly = false,
	fontSize = 12,
}: SourceCodeEditorProps) {
	const { resolvedTheme } = useTheme();

	return (
		<div className="h-full w-full overflow-hidden bg-sidebar">
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
					wordWrap: "off",
					scrollbar: {
						vertical: "hidden",
						horizontal: "hidden",
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
