"use client";

import { DownloadIcon, PauseIcon, PlayIcon, Volume2Icon, VolumeXIcon } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

interface AudioProps {
	id: string;
	assetId?: string;
	src: string;
	title: string;
	description?: string;
	artwork?: string;
	durationMs?: number;
	className?: string;
}

function formatTime(seconds: number): string {
	if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
	const mins = Math.floor(seconds / 60);
	const secs = Math.floor(seconds % 60);
	return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function Audio({ id, src, title, description, artwork, durationMs, className }: AudioProps) {
	const audioRef = useRef<HTMLAudioElement>(null);
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
		try {
			const response = await fetch(src);
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
			console.error("Error downloading audio:", err);
		}
	}, [src, title]);

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
					"flex items-center gap-4 rounded-xl border border-destructive/20 bg-destructive/5 p-4",
					className
				)}
			>
				<div className="flex size-16 items-center justify-center rounded-lg bg-destructive/10">
					<Volume2Icon className="size-8 text-destructive" />
				</div>
				<div className="flex-1">
					<p className="font-medium text-destructive">{title}</p>
					<p className="text-destructive/70 text-sm">{error}</p>
				</div>
			</div>
		);
	}

	return (
		<div
			id={id}
			className={cn(
				"group relative overflow-hidden rounded-xl border bg-gradient-to-br from-background to-muted/30 p-4 shadow-sm transition-all hover:shadow-md",
				className
			)}
		>
			{/* Hidden audio element */}
			<audio ref={audioRef} src={src} preload="metadata">
				<track kind="captions" srcLang="en" label="English captions" default />
			</audio>

			<div className="flex gap-4">
				{/* Artwork */}
				<div className="relative shrink-0">
					<div className="relative size-20 overflow-hidden rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 shadow-inner">
						{artwork ? (
							<Image src={artwork} alt={title} fill className="object-cover" unoptimized />
						) : (
							<div className="flex size-full items-center justify-center">
								<Volume2Icon className="size-8 text-primary/50" />
							</div>
						)}
					</div>
				</div>

				{/* Content */}
				<div className="flex min-w-0 flex-1 flex-col justify-between">
					{/* Title and description */}
					<div className="min-w-0">
						<h3 className="truncate font-semibold text-foreground">{title}</h3>
						{description && (
							<p className="mt-0.5 line-clamp-1 text-muted-foreground text-sm">{description}</p>
						)}
					</div>

					{/* Progress bar */}
					<div className="mt-2 space-y-1">
						<Slider
							value={[currentTime]}
							max={duration || 100}
							step={0.1}
							onValueChange={handleSeek}
							className="cursor-pointer"
							disabled={isLoading}
						/>
						<div className="flex justify-between text-muted-foreground text-xs">
							<span>{formatTime(currentTime)}</span>
							<span>{formatTime(duration)}</span>
						</div>
					</div>
				</div>
			</div>

			{/* Controls */}
			<div className="mt-3 flex items-center justify-between border-t pt-3">
				<div className="flex items-center gap-2">
					{/* Play/Pause button */}
					<Button
						variant="default"
						size="sm"
						onClick={togglePlayPause}
						disabled={isLoading}
						className="gap-2"
					>
						{isLoading ? (
							<div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
						) : isPlaying ? (
							<PauseIcon className="size-4" />
						) : (
							<PlayIcon className="size-4" />
						)}
						{isPlaying ? "Pause" : "Play"}
					</Button>

					{/* Volume control */}
					<div className="flex items-center gap-1.5">
						<Button variant="ghost" size="icon" onClick={toggleMute} className="size-8">
							{isMuted ? <VolumeXIcon className="size-4" /> : <Volume2Icon className="size-4" />}
						</Button>
						{/* Custom volume bar - visually distinct from progress slider */}
						<div className="relative flex h-6 w-16 items-center">
							<div className="relative h-1 w-full rounded-full bg-muted-foreground/20">
								<div
									className="absolute left-0 top-0 h-full rounded-full bg-muted-foreground/60 transition-all"
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

				{/* Download button */}
				<Button variant="outline" size="sm" onClick={handleDownload} className="gap-2">
					<DownloadIcon className="size-4" />
					Download
				</Button>
			</div>
		</div>
	);
}
