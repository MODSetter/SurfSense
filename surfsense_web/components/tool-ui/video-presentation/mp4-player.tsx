export interface Mp4VideoPlayerProps {
	src: string;
	poster?: string;
}

export function Mp4VideoPlayer({ src, poster }: Mp4VideoPlayerProps) {
	return (
		// Generated MP4 artifacts do not include a captions file.
		// biome-ignore lint/a11y/useMediaCaption: A synthetic empty track would misrepresent availability.
		<video
			className="block aspect-video max-h-full w-full bg-black object-contain"
			controls
			playsInline
			preload="none"
			poster={poster}
			src={src}
		/>
	);
}
