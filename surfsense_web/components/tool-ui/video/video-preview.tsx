"use client";

import { Player, type ErrorFallback } from "@remotion/player";
import type React from "react";
import { useEffect, useState } from "react";
import { compileCode } from "@/app/remotion/compiler";

const PLAYER_STYLE = {
	backgroundColor: "#0a0a0f",
	display: "flex",
	alignItems: "center",
	justifyContent: "center",
	width: "100%",
	aspectRatio: "16/9",
	borderRadius: 8,
} as const;

const runtimeErrorFallback: ErrorFallback = ({ error }) => (
	<div
		style={{
			...PLAYER_STYLE,
			flexDirection: "column",
			gap: 8,
			color: "#ff6b6b",
			fontFamily: "monospace",
			fontSize: 13,
			padding: 24,
			wordBreak: "break-word",
			textAlign: "center",
		}}
	>
		<span style={{ fontSize: 15, fontWeight: 600 }}>Runtime error</span>
		<span>{error.message}</span>
	</div>
);

export const VideoPreview = ({
	code,
	durationInFrames = 180,
}: {
	code: string;
	durationInFrames?: number;
}) => {
	const [Component, setComponent] = useState<React.ComponentType | null>(null);
	const [compilationError, setCompilationError] = useState<string | null>(null);

	useEffect(() => {
		setComponent(null);
		setCompilationError(null);
		const result = compileCode(code);
		if (result.error) {
			setCompilationError(result.error);
		} else {
			setComponent(() => result.Component);
		}
	}, [code]);

	if (compilationError) {
		return (
			<div
				style={{
					...PLAYER_STYLE,
					flexDirection: "column",
					gap: 8,
					color: "#ff6b6b",
					fontFamily: "monospace",
					fontSize: 13,
					padding: 24,
					wordBreak: "break-word",
					textAlign: "center",
				}}
			>
				<span style={{ fontSize: 15, fontWeight: 600 }}>Compilation error</span>
				<span>{compilationError}</span>
			</div>
		);
	}

	if (!Component) {
		return (
			<div style={PLAYER_STYLE}>
				<div className="size-8 animate-spin rounded-full border-4 border-border border-t-muted-foreground" />
			</div>
		);
	}

	return (
		<Player
			component={Component}
			durationInFrames={durationInFrames}
			fps={30}
			compositionWidth={1920}
			compositionHeight={1080}
			style={{ width: "100%", borderRadius: 8 }}
			errorFallback={runtimeErrorFallback}
			controls
			autoPlay
			loop
		/>
	);
};
