"use client";

import { Pause, Play, Podcast, SkipBack, SkipForward, Volume2, VolumeX, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { PodcastItem } from "@/app/dashboard/[search_space_id]/podcasts/podcasts-client";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { PodcastPlayerCompactSkeleton } from "./PodcastPlayerCompactSkeleton";

interface PodcastPlayerProps {
	podcast: PodcastItem | null;
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
				const token = localStorage.getItem("surfsense_bearer_token");
				if (!token) {
					throw new Error("Authentication token not found.");
				}

				// Revoke previous object URL if exists
				if (currentObjectUrlRef.current) {
					URL.revokeObjectURL(currentObjectUrlRef.current);
					currentObjectUrlRef.current = null;
				}

				const controller = new AbortController();
				const timeoutId = setTimeout(() => controller.abort(), 30000);

				try {
					const response = await fetch(
						`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcast.id}/stream`,
						{
							headers: {
								Authorization: `Bearer ${token}`,
							},
							signal: controller.signal,
						}
					);

					if (!response.ok) {
						throw new Error(`Failed to fetch audio stream: ${response.statusText}`);
					}

					const blob = await response.blob();
					const objectUrl = URL.createObjectURL(blob);
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
				<div className="flex flex-col gap-3 p-3">
					<div className="flex items-center gap-2">
						<motion.div
							className="w-8 h-8 bg-primary/20 rounded-md flex items-center justify-center flex-shrink-0"
							animate={{ scale: isPlaying ? [1, 1.05, 1] : 1 }}
							transition={{
								repeat: isPlaying ? Infinity : 0,
								duration: 2,
							}}
						>
							<Podcast className="h-4 w-4 text-primary" />
						</motion.div>
						<h4 className="font-medium text-xs line-clamp-1 flex-grow">{podcast.title}</h4>
						{onClose && (
							<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
								<Button
									variant="ghost"
									size="icon"
									onClick={onClose}
									className="h-6 w-6 flex-shrink-0"
								>
									<X className="h-3 w-3" />
								</Button>
							</motion.div>
						)}
					</div>

					<div className="flex items-center gap-1">
						<Slider
							value={[currentTime]}
							min={0}
							max={duration || 100}
							step={0.1}
							onValueChange={handleSeek}
							className="flex-grow"
						/>
						<div className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">
							{formatTime(currentTime)} / {formatTime(duration)}
						</div>
					</div>

					<div className="flex items-center justify-between gap-1">
						<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
							<Button
								variant="ghost"
								size="icon"
								onClick={skipBackward}
								className="h-7 w-7"
								disabled={!duration}
							>
								<SkipBack className="h-3 w-3" />
							</Button>
						</motion.div>

						<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
							<Button
								variant="default"
								size="icon"
								onClick={togglePlayPause}
								className="h-8 w-8 rounded-full"
								disabled={!duration}
							>
								{isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
							</Button>
						</motion.div>

						<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
							<Button
								variant="ghost"
								size="icon"
								onClick={skipForward}
								className="h-7 w-7"
								disabled={!duration}
							>
								<SkipForward className="h-3 w-3" />
							</Button>
						</motion.div>

						<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
							<Button
								variant="ghost"
								size="icon"
								onClick={toggleMute}
								className={`h-7 w-7 ${isMuted ? "text-muted-foreground" : "text-primary"}`}
							>
								{isMuted ? <VolumeX className="h-3 w-3" /> : <Volume2 className="h-3 w-3" />}
							</Button>
						</motion.div>
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
