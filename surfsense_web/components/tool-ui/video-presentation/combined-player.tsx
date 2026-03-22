"use client";

import React, { useMemo } from "react";
import { Player } from "@remotion/player";
import { Sequence, AbsoluteFill } from "remotion";
import { Audio } from "@remotion/media";
import { FPS } from "@/lib/remotion/constants";

export interface CompiledSlide {
	component: React.ComponentType;
	title: string;
	code: string;
	durationInFrames: number;
	audioUrl?: string;
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
		[slides],
	);

	return (
		<div className="overflow-hidden rounded-xl border shadow-2xl shadow-purple-500/5">
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
