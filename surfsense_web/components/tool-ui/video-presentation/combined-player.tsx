"use client";

import { Audio } from "@remotion/media";
import { Player } from "@remotion/player";
import type React from "react";
import { useMemo } from "react";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { FPS } from "@/lib/remotion/constants";

export interface CompiledSlide {
	component: React.ComponentType;
	title: string;
	code: string;
	durationInFrames: number;
	audioUrl?: string;
}

const WATERMARK_STYLES = {
	container: {
		position: "absolute" as const,
		bottom: 28,
		right: 36,
		display: "flex",
		alignItems: "center",
		gap: 8,
		padding: "6px 14px 6px 10px",
		borderRadius: 9999,
		background: "rgba(0, 0, 0, 0.35)",
		backdropFilter: "blur(12px)",
		WebkitBackdropFilter: "blur(12px)",
		border: "1px solid rgba(255, 255, 255, 0.12)",
		boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
		pointerEvents: "none" as const,
		zIndex: 9999,
	},
	logo: {
		width: 22,
		height: 22,
		filter: "brightness(0) invert(1)",
	},
	text: {
		fontFamily: "Inter, system-ui, -apple-system, sans-serif",
		fontSize: 15,
		fontWeight: 600,
		color: "rgba(255, 255, 255, 0.95)",
		letterSpacing: "0.01em",
		lineHeight: 1,
	},
};

function Watermark() {
	const frame = useCurrentFrame();
	const { fps } = useVideoConfig();

	const opacity = interpolate(frame, [0, fps * 0.5], [0, 1], {
		extrapolateRight: "clamp",
	});

	return (
		<div style={{ ...WATERMARK_STYLES.container, opacity }}>
			{/* eslint-disable-next-line @next/next/no-img-element */}
			<img src="/icon-128.svg" alt="" style={WATERMARK_STYLES.logo} />
			<span style={WATERMARK_STYLES.text}>SurfSense</span>
		</div>
	);
}

export function buildSlideWithWatermark(SlideComponent: React.ComponentType): React.FC {
	const Wrapped: React.FC = () => (
		<AbsoluteFill>
			<SlideComponent />
			<Watermark />
		</AbsoluteFill>
	);
	return Wrapped;
}

function CombinedComposition({ scenes }: { scenes: CompiledSlide[] }) {
	let offset = 0;

	return (
		<AbsoluteFill>
			{scenes.map((scene, i) => {
				const from = offset;
				offset += scene.durationInFrames;
				return (
					<Sequence key={i} from={from} durationInFrames={scene.durationInFrames}>
						<scene.component />
						{scene.audioUrl && <Audio src={scene.audioUrl} />}
					</Sequence>
				);
			})}
			<Watermark />
		</AbsoluteFill>
	);
}

export function buildCompositionComponent(slides: CompiledSlide[]): React.FC {
	const scenesSnapshot = [...slides];
	const Comp: React.FC = () => <CombinedComposition scenes={scenesSnapshot} />;
	return Comp;
}

interface CombinedPlayerProps {
	slides: CompiledSlide[];
}

export function CombinedPlayer({ slides }: CombinedPlayerProps) {
	const CompositionWithScenes = useMemo(() => {
		const scenesSnapshot = [...slides];
		const Comp: React.FC = () => <CombinedComposition scenes={scenesSnapshot} />;
		return Comp;
	}, [slides]);

	const totalFrames = useMemo(
		() => slides.reduce((sum, s) => sum + s.durationInFrames, 0),
		[slides]
	);

	return (
		<div className="overflow-hidden rounded-xl">
			<Player
				component={CompositionWithScenes}
				durationInFrames={totalFrames}
				fps={FPS}
				compositionWidth={1920}
				compositionHeight={1080}
				style={{ width: "100%", aspectRatio: "16/9" }}
				controls
				autoPlay
				loop
				acknowledgeRemotionLicense
			/>
		</div>
	);
}
