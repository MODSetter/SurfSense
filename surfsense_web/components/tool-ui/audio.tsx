"use client";

import { DownloadIcon, PauseIcon, PlayIcon, Volume2Icon, VolumeXIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

interface AudioProps {
	id: string;
	assetId?: string;
	src: string;
	title: string;
	durationMs?: number;
	className?: string;
}

function formatTime(seconds: number): string {
	if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
	const mins = Math.floor(seconds / 60);
	const secs = Math.floor(seconds % 60);
	return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function Audio({ id, src, title, durationMs, className }: AudioProps) {
	const audioRef = useRef<HTMLAudioElement>(null);
	const downloadControllerRef = useRef<AbortController | null>(null);
	const [isPlaying, setIsPlaying] = useState(false);
	const [currentTime, setCurrentTime] = useState(0);
	const [duration, setDuration] = useState(durationMs ? durationMs / 1000 : 0);
	const [volume, setVolume] = useState(1);
	const [isMuted, setIsMuted] = useState(false);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	// Handle play/pause
	const togglePlayPause = useCallback(() => {
		const audio = audioRef.current;
		if (!audio) return;

		if (isPlaying) {
			audio.pause();
		} else {
			audio.play().catch((err) => {
				console.error("Error playing audio:", err);
				setError("Failed to play audio");
			});
		}
	}, [isPlaying]);

	// Handle seek
	const handleSeek = useCallback((value: number[]) => {
		const audio = audioRef.current;
		if (!audio || !Number.isFinite(value[0])) return;
		audio.currentTime = value[0];
		setCurrentTime(value[0]);
	}, []);

	// Handle volume change
	const handleVolumeChange = useCallback((value: number[]) => {
		const audio = audioRef.current;
		if (!audio || !Number.isFinite(value[0])) return;
		const newVolume = value[0];
		audio.volume = newVolume;
		setVolume(newVolume);
		setIsMuted(newVolume === 0);
	}, []);

	// Toggle mute
	const toggleMute = useCallback(() => {
		const audio = audioRef.current;
		if (!audio) return;

		if (isMuted) {
			audio.volume = volume || 1;
			setIsMuted(false);
		} else {
			audio.volume = 0;
			setIsMuted(true);
		}
	}, [isMuted, volume]);

	// Handle download
	const handleDownload = useCallback(async () => {
		downloadControllerRef.current?.abort();
		const controller = new AbortController();
		downloadControllerRef.current = controller;

		try {
			const response = await fetch(src, { signal: controller.signal });
			const blob = await response.blob();
			const url = window.URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `${title.replace(/[^a-zA-Z0-9]/g, "_")}.mp3`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			window.URL.revokeObjectURL(url);
		} catch (err) {
			if (err instanceof DOMException && err.name === "AbortError") return;
			console.error("Error downloading audio:", err);
		}
	}, [src, title]);

	// Abort in-flight download on unmount
	useEffect(() => {
		return () => downloadControllerRef.current?.abort();
	}, []);

	// Set up audio event listeners
	useEffect(() => {
		const audio = audioRef.current;
		if (!audio) return;

		const handleLoadedMetadata = () => {
			setDuration(audio.duration);
			setIsLoading(false);
		};

		const handleTimeUpdate = () => {
			setCurrentTime(audio.currentTime);
		};

		const handlePlay = () => setIsPlaying(true);
		const handlePause = () => setIsPlaying(false);
		const handleEnded = () => {
			setIsPlaying(false);
			setCurrentTime(0);
		};
		const handleError = () => {
			setError("Failed to load audio");
			setIsLoading(false);
		};
		const handleCanPlay = () => setIsLoading(false);

		audio.addEventListener("loadedmetadata", handleLoadedMetadata);
		audio.addEventListener("timeupdate", handleTimeUpdate);
		audio.addEventListener("play", handlePlay);
		audio.addEventListener("pause", handlePause);
		audio.addEventListener("ended", handleEnded);
		audio.addEventListener("error", handleError);
		audio.addEventListener("canplay", handleCanPlay);

		return () => {
			audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
			audio.removeEventListener("timeupdate", handleTimeUpdate);
			audio.removeEventListener("play", handlePlay);
			audio.removeEventListener("pause", handlePause);
			audio.removeEventListener("ended", handleEnded);
			audio.removeEventListener("error", handleError);
			audio.removeEventListener("canplay", handleCanPlay);
		};
	}, []);

	if (error) {
		return (
			<div
				className={cn(
					"max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none",
					className
				)}
			>
				<div className="px-5 pt-5 pb-4">
					<p className="text-sm font-semibold text-destructive">Audio Error</p>
				</div>
				<div className="mx-5 h-px bg-border/50" />
				<div className="px-5 py-4">
					<p className="text-sm font-medium text-foreground truncate">{title}</p>
					<p className="text-sm text-muted-foreground mt-1">{error}</p>
				</div>
			</div>
		);
	}

	return (
		<div
			id={id}
			className={cn(
				"max-w-lg overflow-hidden rounded-2xl border bg-muted/30 select-none",
				className
			)}
		>
			<audio ref={audioRef} src={src} preload="metadata">
				<track kind="captions" srcLang="en" label="English captions" default />
			</audio>

			<div className="flex items-start gap-2 px-5 pt-5 pb-4">
				<p className="text-sm font-semibold text-foreground line-clamp-2 flex-1 min-w-0">{title}</p>
				<Button
					variant="ghost"
					size="icon"
					onClick={handleDownload}
					className="size-7 shrink-0 -mt-0.5 -mr-2 text-muted-foreground"
					aria-label="Download audio"
				>
					<DownloadIcon className="size-4" />
				</Button>
			</div>

			<div className="mx-5 h-px bg-border/50" />

			<div className="px-5 pt-3 pb-4 space-y-3">
				<div className="space-y-0.5">
					<Slider
						value={[currentTime]}
						max={duration || 100}
						step={0.1}
						onValueChange={handleSeek}
						className="cursor-pointer [&_[role=slider]]:border-0 [&_[role=slider]]:!bg-muted-foreground [&_[role=slider]]:h-4 [&_[role=slider]]:w-4 [&>span>span:first-child]:bg-muted-foreground/60"
						disabled={isLoading}
					/>
					<div className="flex justify-between text-muted-foreground text-[10px] sm:text-xs">
						<span>{formatTime(currentTime)}</span>
						<span>{formatTime(duration)}</span>
					</div>
				</div>

				<div className="flex items-center gap-1.5 sm:gap-2">
					<Button
						variant="secondary"
						size="icon"
						onClick={togglePlayPause}
						disabled={isLoading}
						className="size-7 sm:size-8"
						aria-label={isPlaying ? "Pause" : "Play"}
					>
						{isLoading ? (
							<div className="size-3 sm:size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
						) : isPlaying ? (
							<PauseIcon className="size-3.5 sm:size-4" fill="currentColor" />
						) : (
							<PlayIcon className="size-3.5 sm:size-4" fill="currentColor" />
						)}
					</Button>

					<div className="group/volume flex items-center gap-1 sm:gap-1.5">
						<Button
							variant="ghost"
							size="icon"
							onClick={toggleMute}
							className="size-7 sm:size-8"
							aria-label={isMuted ? "Unmute" : "Mute"}
						>
							{isMuted ? (
								<VolumeXIcon className="size-3.5 sm:size-4" />
							) : (
								<Volume2Icon className="size-3.5 sm:size-4" />
							)}
						</Button>
						<div className="relative hidden h-6 w-16 items-center md:flex md:opacity-0 md:pointer-events-none md:group-hover/volume:opacity-100 md:group-hover/volume:pointer-events-auto md:transition-opacity md:duration-200">
							<div className="relative h-1 w-full rounded-full bg-muted-foreground/20">
								<div
									className="absolute left-0 top-0 h-full rounded-full bg-muted-foreground/60 transition-[width]"
									style={{ width: `${(isMuted ? 0 : volume) * 100}%` }}
								/>
							</div>
							<input
								type="range"
								min={0}
								max={1}
								step={0.01}
								value={isMuted ? 0 : volume}
								onChange={(e) => handleVolumeChange([Number.parseFloat(e.target.value)])}
								className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
								aria-label="Volume"
							/>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
