"use client";

import dynamic from "next/dynamic";
import { useTheme } from "next-themes";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
	ssr: false,
});

interface LocalFileMonacoProps {
	filePath: string;
	language: string;
	value: string;
	onChange: (next: string) => void;
}

export function LocalFileMonaco({ filePath, language, value, onChange }: LocalFileMonacoProps) {
	const { resolvedTheme } = useTheme();

	return (
		<div className="h-full w-full overflow-hidden bg-sidebar">
			<MonacoEditor
				path={filePath}
				language={language}
				value={value}
				theme={resolvedTheme === "dark" ? "vs-dark" : "vs"}
				onChange={(next) => onChange(next ?? "")}
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
					fontSize: 12,
					fontFamily:
						"ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace",
					renderWhitespace: "selection",
					smoothScrolling: true,
				}}
			/>
		</div>
	);
}
