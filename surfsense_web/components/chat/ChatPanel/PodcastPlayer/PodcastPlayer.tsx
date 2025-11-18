"use client";

import { Pause, Play, SkipBack, SkipForward, Volume2, VolumeX, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { Podcast } from "@/contracts/types/podcast.types";
import { podcastsApiService } from "@/lib/apis/podcasts-api.service";
import { PodcastPlayerCompactSkeleton } from "./PodcastPlayerCompactSkeleton";

interface PodcastPlayerProps {
	podcast: Podcast | null;
	isLoading?: boolean;
	onClose?: () => void;
	compact?: boolean;
}

export function PodcastPlayer({
	podcast,
	isLoading = false,
	onClose,
	compact = false,
}: PodcastPlayerProps) {
	const [audioSrc, setAudioSrc] = useState<string | undefined>(undefined);
	const [isPlaying, setIsPlaying] = useState(false);
	const [currentTime, setCurrentTime] = useState(0);
	const [duration, setDuration] = useState(0);
	const [volume, setVolume] = useState(0.7);
	const [isMuted, setIsMuted] = useState(false);
	const [isFetching, setIsFetching] = useState(false);
	const audioRef = useRef<HTMLAudioElement | null>(null);
	const currentObjectUrlRef = useRef<string | null>(null);

	// Cleanup object URL on unmount
	useEffect(() => {
		return () => {
			if (currentObjectUrlRef.current) {
				URL.revokeObjectURL(currentObjectUrlRef.current);
				currentObjectUrlRef.current = null;
			}
		};
	}, []);

	// Load podcast audio when podcast changes
	useEffect(() => {
		if (!podcast) {
			setAudioSrc(undefined);
			setCurrentTime(0);
			setDuration(0);
			setIsPlaying(false);
			setIsFetching(false);
			return;
		}

		const loadPodcast = async () => {
			setIsFetching(true);
			try {
				// Revoke previous object URL if exists
				if (currentObjectUrlRef.current) {
					URL.revokeObjectURL(currentObjectUrlRef.current);
					currentObjectUrlRef.current = null;
				}

				const controller = new AbortController();
				const timeoutId = setTimeout(() => controller.abort(), 30000);

				try {
					const response = await podcastsApiService.loadPodcast({
						request: { id: podcast.id },
						controller,
					});

					const objectUrl = URL.createObjectURL(response);
					currentObjectUrlRef.current = objectUrl;
					setAudioSrc(objectUrl);
				} catch (error) {
					if (error instanceof DOMException && error.name === "AbortError") {
						throw new Error("Request timed out. Please try again.");
					}
					throw error;
				} finally {
					clearTimeout(timeoutId);
				}
			} catch (error) {
				console.error("Error fetching podcast:", error);
				toast.error(error instanceof Error ? error.message : "Failed to load podcast audio.");
				setAudioSrc(undefined);
			} finally {
				setIsFetching(false);
			}
		};

		loadPodcast();
	}, [podcast]);

	const handleTimeUpdate = () => {
		if (audioRef.current) {
			setCurrentTime(audioRef.current.currentTime);
		}
	};

	const handleMetadataLoaded = () => {
		if (audioRef.current) {
			setDuration(audioRef.current.duration);
		}
	};

	const togglePlayPause = () => {
		if (audioRef.current) {
			if (isPlaying) {
				audioRef.current.pause();
			} else {
				audioRef.current.play();
			}
			setIsPlaying(!isPlaying);
		}
	};

	const handleSeek = (value: number[]) => {
		if (audioRef.current) {
			audioRef.current.currentTime = value[0];
			setCurrentTime(value[0]);
		}
	};

	const handleVolumeChange = (value: number[]) => {
		if (audioRef.current) {
			const newVolume = value[0];
			audioRef.current.volume = newVolume;
			setVolume(newVolume);

			if (newVolume === 0) {
				audioRef.current.muted = true;
				setIsMuted(true);
			} else {
				audioRef.current.muted = false;
				setIsMuted(false);
			}
		}
	};

	const toggleMute = () => {
		if (audioRef.current) {
			const newMutedState = !isMuted;
			audioRef.current.muted = newMutedState;
			setIsMuted(newMutedState);

			if (!newMutedState && volume === 0) {
				const restoredVolume = 0.5;
				audioRef.current.volume = restoredVolume;
				setVolume(restoredVolume);
			}
		}
	};

	const skipForward = () => {
		if (audioRef.current) {
			audioRef.current.currentTime = Math.min(
				audioRef.current.duration,
				audioRef.current.currentTime + 10
			);
		}
	};

	const skipBackward = () => {
		if (audioRef.current) {
			audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 10);
		}
	};

	const formatTime = (time: number) => {
		const minutes = Math.floor(time / 60);
		const seconds = Math.floor(time % 60);
		return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
	};

	// Show skeleton while fetching
	if (isFetching && compact) {
		return <PodcastPlayerCompactSkeleton />;
	}

	if (!podcast || !audioSrc) {
		return null;
	}

	if (compact) {
		return (
			<>
				<div className="flex flex-col gap-4 p-4">
					{/* Audio Visualizer */}
					<motion.div
						className="relative h-1 bg-gradient-to-r from-primary/20 via-primary/40 to-primary/20 rounded-full overflow-hidden"
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						transition={{ duration: 0.5 }}
					>
						{isPlaying && (
							<motion.div
								className="absolute inset-0 bg-gradient-to-r from-transparent via-primary to-transparent"
								animate={{
									x: ["-100%", "100%"],
								}}
								transition={{
									duration: 2,
									repeat: Infinity,
									ease: "linear",
								}}
							/>
						)}
					</motion.div>

					{/* Progress Bar with Time */}
					<div className="space-y-2">
						<Slider
							value={[currentTime]}
							min={0}
							max={duration || 100}
							step={0.1}
							onValueChange={handleSeek}
							className="w-full cursor-pointer"
						/>
						<div className="flex items-center justify-between text-xs text-muted-foreground">
							<span className="font-mono">{formatTime(currentTime)}</span>
							<span className="font-mono">{formatTime(duration)}</span>
						</div>
					</div>

					{/* Controls */}
					<div className="flex items-center justify-between">
						{/* Left: Volume */}
						<div className="flex items-center gap-2 flex-1">
							<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
								<Button variant="ghost" size="icon" onClick={toggleMute} className="h-8 w-8">
									{isMuted ? (
										<VolumeX className="h-4 w-4 text-muted-foreground" />
									) : (
										<Volume2 className="h-4 w-4" />
									)}
								</Button>
							</motion.div>
						</div>

						{/* Center: Playback Controls */}
						<div className="flex items-center gap-1">
							<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
								<Button
									variant="ghost"
									size="icon"
									onClick={skipBackward}
									className="h-9 w-9"
									disabled={!duration}
								>
									<SkipBack className="h-4 w-4" />
								</Button>
							</motion.div>

							<motion.div
								whileHover={{ scale: 1.05 }}
								whileTap={{ scale: 0.95 }}
								animate={
									isPlaying
										? {
												boxShadow: [
													"0 0 0 0 rgba(var(--primary), 0)",
													"0 0 0 8px rgba(var(--primary), 0.1)",
													"0 0 0 0 rgba(var(--primary), 0)",
												],
											}
										: {}
								}
								transition={{ duration: 1.5, repeat: isPlaying ? Infinity : 0 }}
							>
								<Button
									variant="default"
									size="icon"
									onClick={togglePlayPause}
									className="h-10 w-10 rounded-full"
									disabled={!duration}
								>
									{isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
								</Button>
							</motion.div>

							<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
								<Button
									variant="ghost"
									size="icon"
									onClick={skipForward}
									className="h-9 w-9"
									disabled={!duration}
								>
									<SkipForward className="h-4 w-4" />
								</Button>
							</motion.div>
						</div>

						{/* Right: Placeholder for symmetry */}
						<div className="flex-1" />
					</div>
				</div>

				<audio
					ref={audioRef}
					src={audioSrc}
					preload="auto"
					onTimeUpdate={handleTimeUpdate}
					onLoadedMetadata={handleMetadataLoaded}
					onEnded={() => setIsPlaying(false)}
					onError={(e) => {
						console.error("Audio error:", e);
						if (audioRef.current?.error) {
							console.error("Audio error code:", audioRef.current.error.code);
							if (audioRef.current.error.code !== audioRef.current.error.MEDIA_ERR_ABORTED) {
								toast.error("Error playing audio. Please try again.");
							}
						}
						setIsPlaying(false);
					}}
				>
					<track kind="captions" />
				</audio>
			</>
		);
	}

	return null;
}
