"use client";

import { format } from "date-fns";
import {
	Calendar,
	MoreHorizontal,
	Pause,
	Play,
	Podcast,
	Search,
	SkipBack,
	SkipForward,
	Trash2,
	Volume2,
	VolumeX,
	X,
} from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
// UI Components
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";

interface PodcastItem {
	id: number;
	title: string;
	created_at: string;
	file_location: string;
	podcast_transcript: any[];
	search_space_id: number;
}

interface PodcastsPageClientProps {
	searchSpaceId: string;
}

const pageVariants: Variants = {
	initial: { opacity: 0 },
	enter: {
		opacity: 1,
		transition: { duration: 0.4, ease: "easeInOut", staggerChildren: 0.1 },
	},
	exit: { opacity: 0, transition: { duration: 0.3, ease: "easeInOut" } },
};

const podcastCardVariants: Variants = {
	initial: { scale: 0.95, y: 20, opacity: 0 },
	animate: {
		scale: 1,
		y: 0,
		opacity: 1,
		transition: { type: "spring", stiffness: 300, damping: 25 },
	},
	exit: { scale: 0.95, y: -20, opacity: 0 },
	hover: { y: -5, scale: 1.02, transition: { duration: 0.2 } },
};

const MotionCard = motion(Card);

export default function PodcastsPageClient({ searchSpaceId }: PodcastsPageClientProps) {
	const [podcasts, setPodcasts] = useState<PodcastItem[]>([]);
	const [filteredPodcasts, setFilteredPodcasts] = useState<PodcastItem[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [sortOrder, setSortOrder] = useState<string>("newest");
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [podcastToDelete, setPodcastToDelete] = useState<{
		id: number;
		title: string;
	} | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	// Audio player state
	const [currentPodcast, setCurrentPodcast] = useState<PodcastItem | null>(null);
	const [audioSrc, setAudioSrc] = useState<string | undefined>(undefined);
	const [isAudioLoading, setIsAudioLoading] = useState(false);
	const [isPlaying, setIsPlaying] = useState(false);
	const [currentTime, setCurrentTime] = useState(0);
	const [duration, setDuration] = useState(0);
	const [volume, setVolume] = useState(0.7);
	const [isMuted, setIsMuted] = useState(false);
	const audioRef = useRef<HTMLAudioElement | null>(null);
	const currentObjectUrlRef = useRef<string | null>(null);

	// Add podcast image URL constant
	const PODCAST_IMAGE_URL =
		"https://static.vecteezy.com/system/resources/thumbnails/002/157/611/small_2x/illustrations-concept-design-podcast-channel-free-vector.jpg";

	// Fetch podcasts from API
	useEffect(() => {
		const fetchPodcasts = async () => {
			try {
				setIsLoading(true);

				// Get token from localStorage
				const token = localStorage.getItem("surfsense_bearer_token");

				if (!token) {
					setError("Authentication token not found. Please log in again.");
					setIsLoading(false);
					return;
				}

				// Fetch all podcasts for this search space
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts`,
					{
						headers: {
							Authorization: `Bearer ${token}`,
							"Content-Type": "application/json",
						},
						cache: "no-store",
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => null);
					throw new Error(
						`Failed to fetch podcasts: ${response.status} ${errorData?.detail || ""}`
					);
				}

				const data: PodcastItem[] = await response.json();
				setPodcasts(data);
				setFilteredPodcasts(data);
				setError(null);
			} catch (error) {
				console.error("Error fetching podcasts:", error);
				setError(error instanceof Error ? error.message : "Unknown error occurred");
				setPodcasts([]);
				setFilteredPodcasts([]);
			} finally {
				setIsLoading(false);
			}
		};

		fetchPodcasts();
	}, []);

	// Filter and sort podcasts based on search query and sort order
	useEffect(() => {
		let result = [...podcasts];

		// Filter by search term
		if (searchQuery) {
			const query = searchQuery.toLowerCase();
			result = result.filter((podcast) => podcast.title.toLowerCase().includes(query));
		}

		// Filter by search space
		result = result.filter((podcast) => podcast.search_space_id === parseInt(searchSpaceId));

		// Sort podcasts
		result.sort((a, b) => {
			const dateA = new Date(a.created_at).getTime();
			const dateB = new Date(b.created_at).getTime();

			return sortOrder === "newest" ? dateB - dateA : dateA - dateB;
		});

		setFilteredPodcasts(result);
	}, [podcasts, searchQuery, sortOrder, searchSpaceId]);

	// Cleanup object URL on unmount or when currentPodcast changes
	useEffect(() => {
		return () => {
			if (currentObjectUrlRef.current) {
				URL.revokeObjectURL(currentObjectUrlRef.current);
				currentObjectUrlRef.current = null;
			}
		};
	}, []);

	// Audio player time update handler
	const handleTimeUpdate = () => {
		if (audioRef.current) {
			setCurrentTime(audioRef.current.currentTime);
		}
	};

	// Audio player metadata loaded handler
	const handleMetadataLoaded = () => {
		if (audioRef.current) {
			setDuration(audioRef.current.duration);
		}
	};

	// Play/pause toggle
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

	// To close player
	const closePlayer = () => {
		if (isPlaying) {
			audioRef.current?.pause();
		}
		setIsPlaying(false);
		setAudioSrc(undefined);
		setCurrentTime(0);
		setCurrentPodcast(null);
	};

	// Seek to position
	const handleSeek = (value: number[]) => {
		if (audioRef.current) {
			audioRef.current.currentTime = value[0];
			setCurrentTime(value[0]);
		}
	};

	// Volume change
	const handleVolumeChange = (value: number[]) => {
		if (audioRef.current) {
			const newVolume = value[0];

			// Set volume
			audioRef.current.volume = newVolume;
			setVolume(newVolume);

			// Handle mute state based on volume
			if (newVolume === 0) {
				audioRef.current.muted = true;
				setIsMuted(true);
			} else {
				audioRef.current.muted = false;
				setIsMuted(false);
			}
		}
	};

	// Toggle mute
	const toggleMute = () => {
		if (audioRef.current) {
			const newMutedState = !isMuted;
			audioRef.current.muted = newMutedState;
			setIsMuted(newMutedState);

			// If unmuting, restore previous volume if it was 0
			if (!newMutedState && volume === 0) {
				const restoredVolume = 0.5;
				audioRef.current.volume = restoredVolume;
				setVolume(restoredVolume);
			}
		}
	};

	// Skip forward 10 seconds
	const skipForward = () => {
		if (audioRef.current) {
			audioRef.current.currentTime = Math.min(
				audioRef.current.duration,
				audioRef.current.currentTime + 10
			);
		}
	};

	// Skip backward 10 seconds
	const skipBackward = () => {
		if (audioRef.current) {
			audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 10);
		}
	};

	// Format time in MM:SS
	const formatTime = (time: number) => {
		const minutes = Math.floor(time / 60);
		const seconds = Math.floor(time % 60);
		return `${minutes}:${seconds < 10 ? "0" : ""}${seconds}`;
	};

	// Play podcast - Fetch blob and set object URL
	const playPodcast = async (podcast: PodcastItem) => {
		// If the same podcast is selected, just toggle play/pause
		if (currentPodcast && currentPodcast.id === podcast.id) {
			togglePlayPause();
			return;
		}

		// Prevent multiple simultaneous loading requests
		if (isAudioLoading) {
			return;
		}

		try {
			// Reset player state and show loading
			setCurrentPodcast(podcast);
			setAudioSrc(undefined);
			setCurrentTime(0);
			setDuration(0);
			setIsPlaying(false);
			setIsAudioLoading(true);

			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				throw new Error("Authentication token not found.");
			}

			// Revoke previous object URL if exists (only after we've started the new request)
			if (currentObjectUrlRef.current) {
				URL.revokeObjectURL(currentObjectUrlRef.current);
				currentObjectUrlRef.current = null;
			}

			// Use AbortController to handle timeout or cancellation
			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

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

				// Set audio source
				setAudioSrc(objectUrl);

				// Wait for the audio to be ready before playing
				// We'll handle actual playback in the onLoadedData event instead of here
			} catch (error) {
				if (error instanceof DOMException && error.name === "AbortError") {
					throw new Error("Request timed out. Please try again.");
				}
				throw error;
			} finally {
				clearTimeout(timeoutId);
			}
		} catch (error) {
			console.error("Error fetching or playing podcast:", error);
			toast.error(error instanceof Error ? error.message : "Failed to load podcast audio.");
			// Reset state on error
			setCurrentPodcast(null);
			setAudioSrc(undefined);
		} finally {
			setIsAudioLoading(false);
		}
	};

	// Function to handle podcast deletion
	const handleDeletePodcast = async () => {
		if (!podcastToDelete) return;

		setIsDeleting(true);
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				setIsDeleting(false);
				return;
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcastToDelete.id}`,
				{
					method: "DELETE",
					headers: {
						Authorization: `Bearer ${token}`,
						"Content-Type": "application/json",
					},
				}
			);

			if (!response.ok) {
				throw new Error(`Failed to delete podcast: ${response.statusText}`);
			}

			// Close dialog and refresh podcasts
			setDeleteDialogOpen(false);
			setPodcastToDelete(null);

			// Update local state by removing the deleted podcast
			setPodcasts((prevPodcasts) =>
				prevPodcasts.filter((podcast) => podcast.id !== podcastToDelete.id)
			);

			// If the current playing podcast is deleted, stop playback
			if (currentPodcast && currentPodcast.id === podcastToDelete.id) {
				if (audioRef.current) {
					audioRef.current.pause();
				}
				setCurrentPodcast(null);
				setIsPlaying(false);
			}

			toast.success("Podcast deleted successfully");
		} catch (error) {
			console.error("Error deleting podcast:", error);
			toast.error(error instanceof Error ? error.message : "Failed to delete podcast");
		} finally {
			setIsDeleting(false);
		}
	};

	return (
		<motion.div
			className="container p-6 mx-auto"
			initial="initial"
			animate="enter"
			exit="exit"
			variants={pageVariants}
		>
			<div className="flex flex-col space-y-4 md:space-y-6">
				<div className="flex flex-col space-y-2">
					<h1 className="text-3xl font-bold tracking-tight">Podcasts</h1>
					<p className="text-muted-foreground">Listen to generated podcasts.</p>
				</div>

				{/* Filter and Search Bar */}
				<div className="flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0">
					<div className="flex flex-1 items-center gap-2">
						<div className="relative w-full md:w-80">
							<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
							<Input
								type="text"
								placeholder="Search podcasts..."
								className="pl-8"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
							/>
						</div>
					</div>

					<div>
						<Select value={sortOrder} onValueChange={setSortOrder}>
							<SelectTrigger className="w-40">
								<SelectValue placeholder="Sort order" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectItem value="newest">Newest First</SelectItem>
									<SelectItem value="oldest">Oldest First</SelectItem>
								</SelectGroup>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* Status Messages */}
				{isLoading && (
					<div className="flex items-center justify-center h-40">
						<div className="flex flex-col items-center gap-2">
							<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
							<p className="text-sm text-muted-foreground">Loading podcasts...</p>
						</div>
					</div>
				)}

				{error && !isLoading && (
					<div className="border border-destructive/50 text-destructive p-4 rounded-md">
						<h3 className="font-medium">Error loading podcasts</h3>
						<p className="text-sm">{error}</p>
					</div>
				)}

				{!isLoading && !error && filteredPodcasts.length === 0 && (
					<div className="flex flex-col items-center justify-center h-40 gap-2 text-center">
						<Podcast className="h-8 w-8 text-muted-foreground" />
						<h3 className="font-medium">No podcasts found</h3>
						<p className="text-sm text-muted-foreground">
							{searchQuery
								? "Try adjusting your search filters"
								: "Generate podcasts from your chats to get started"}
						</p>
					</div>
				)}

				{/* Podcast Grid */}
				{!isLoading && !error && filteredPodcasts.length > 0 && (
					<AnimatePresence mode="wait">
						<motion.div
							className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
							variants={pageVariants}
							initial="initial"
							animate="enter"
							exit="exit"
						>
							{filteredPodcasts.map((podcast, index) => (
								<MotionCard
									key={podcast.id}
									variants={podcastCardVariants}
									initial="initial"
									animate="animate"
									exit="exit"
									whileHover="hover"
									transition={{ duration: 0.2, delay: index * 0.05 }}
									className={`
                    bg-card/60 dark:bg-card/40 backdrop-blur-lg rounded-xl p-4 
                    shadow-md hover:shadow-xl transition-all duration-300 
                    border-border overflow-hidden cursor-pointer
                    ${currentPodcast?.id === podcast.id ? "ring-2 ring-primary ring-offset-2 ring-offset-background" : ""}
                  `}
									layout
									onClick={() => playPodcast(podcast)}
								>
									<div className="relative w-full aspect-[16/10] mb-4 rounded-lg overflow-hidden">
										{/* Podcast image with gradient overlay */}
										<Image
											src={PODCAST_IMAGE_URL}
											alt="Podcast illustration"
											className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105 brightness-[0.85] contrast-[1.1]"
											loading="lazy"
											width={100}
											height={100}
										/>

										{/* Better overlay with gradient for improved text legibility */}
										<div className="absolute inset-0 bg-gradient-to-t from-black/60 to-black/10 transition-opacity duration-300"></div>

										{/* Loading indicator with improved animation */}
										{currentPodcast?.id === podcast.id && isAudioLoading && (
											<motion.div
												className="absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-md z-10"
												initial={{ opacity: 0 }}
												animate={{ opacity: 1 }}
												exit={{ opacity: 0 }}
												transition={{ duration: 0.2 }}
											>
												<motion.div
													className="flex flex-col items-center gap-3"
													initial={{ scale: 0.9 }}
													animate={{ scale: 1 }}
													transition={{ type: "spring", damping: 20 }}
												>
													<div className="h-14 w-14 rounded-full border-4 border-primary/30 border-t-primary animate-spin"></div>
													<p className="text-sm text-foreground font-medium">Loading podcast...</p>
												</motion.div>
											</motion.div>
										)}

										{/* Play button with animations */}
										{!(currentPodcast?.id === podcast.id && (isPlaying || isAudioLoading)) && (
											<motion.div
												className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10"
												whileHover={{ scale: 1.1 }}
												whileTap={{ scale: 0.9 }}
											>
												<Button
													variant="secondary"
													size="icon"
													className="h-16 w-16 rounded-full 
                            bg-background/80 hover:bg-background/95 backdrop-blur-md
                            transition-all duration-200 shadow-xl border-0
                            flex items-center justify-center"
													onClick={(e) => {
														e.stopPropagation();
														playPodcast(podcast);
													}}
													disabled={isAudioLoading}
												>
													<motion.div
														initial={{ scale: 0.8 }}
														animate={{ scale: 1 }}
														transition={{
															type: "spring",
															stiffness: 400,
															damping: 10,
														}}
														className="text-primary w-10 h-10 flex items-center justify-center"
													>
														<Play className="h-8 w-8 ml-1" />
													</motion.div>
												</Button>
											</motion.div>
										)}

										{/* Pause button with animations */}
										{currentPodcast?.id === podcast.id && isPlaying && !isAudioLoading && (
											<motion.div
												className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10"
												whileHover={{ scale: 1.1 }}
												whileTap={{ scale: 0.9 }}
											>
												<Button
													variant="secondary"
													size="icon"
													className="h-16 w-16 rounded-full 
                            bg-background/80 hover:bg-background/95 backdrop-blur-md
                            transition-all duration-200 shadow-xl border-0
                            flex items-center justify-center"
													onClick={(e) => {
														e.stopPropagation();
														togglePlayPause();
													}}
													disabled={isAudioLoading}
												>
													<motion.div
														initial={{ scale: 0.8 }}
														animate={{ scale: 1 }}
														transition={{
															type: "spring",
															stiffness: 400,
															damping: 10,
														}}
														className="text-primary w-10 h-10 flex items-center justify-center"
													>
														<Pause className="h-8 w-8" />
													</motion.div>
												</Button>
											</motion.div>
										)}

										{/* Now playing indicator */}
										{currentPodcast?.id === podcast.id && !isAudioLoading && (
											<div className="absolute top-2 left-2 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full z-10 flex items-center gap-1.5">
												<span className="relative flex h-2 w-2">
													<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-foreground opacity-75"></span>
													<span className="relative inline-flex rounded-full h-2 w-2 bg-primary-foreground"></span>
												</span>
												Now Playing
											</div>
										)}
									</div>

									<div className="mb-3 px-1">
										<h3
											className="text-base font-semibold text-foreground truncate"
											title={podcast.title}
										>
											{podcast.title || "Untitled Podcast"}
										</h3>
										<p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
											<Calendar className="h-3 w-3" />
											{format(new Date(podcast.created_at), "MMM d, yyyy")}
										</p>
									</div>

									{currentPodcast?.id === podcast.id && !isAudioLoading && (
										<motion.div
											className="mb-3 px-1"
											initial={{ opacity: 0, y: 5 }}
											animate={{ opacity: 1, y: 0 }}
											transition={{ delay: 0.1 }}
										>
											<Button
												variant="ghost"
												className="h-1.5 bg-muted rounded-full cursor-pointer group relative overflow-hidden"
												onClick={(e) => {
													e.stopPropagation();
													if (!audioRef.current || !duration) return;
													const container = e.currentTarget;
													const rect = container.getBoundingClientRect();
													const x = e.clientX - rect.left;
													const percentage = Math.max(0, Math.min(1, x / rect.width));
													const newTime = percentage * duration;
													handleSeek([newTime]);
												}}
											>
												<motion.div
													className="h-full bg-primary rounded-full relative"
													style={{
														width: `${(currentTime / duration) * 100}%`,
													}}
													transition={{ ease: "linear" }}
												>
													<motion.div
														className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 
                              bg-primary rounded-full shadow-md transform scale-0
                              group-hover:scale-100 transition-transform"
														whileHover={{ scale: 1.5 }}
													/>
												</motion.div>
											</Button>
											<div className="flex justify-between mt-1.5 text-xs text-muted-foreground">
												<span>{formatTime(currentTime)}</span>
												<span>{formatTime(duration)}</span>
											</div>
										</motion.div>
									)}

									{currentPodcast?.id === podcast.id && !isAudioLoading && (
										<motion.div
											className="flex items-center justify-between px-2 mt-1"
											initial={{ opacity: 0, y: 5 }}
											animate={{ opacity: 1, y: 0 }}
											transition={{ delay: 0.2 }}
										>
											<motion.div whileHover={{ scale: 1.2 }} whileTap={{ scale: 0.95 }}>
												<Button
													variant="ghost"
													size="icon"
													onClick={(e) => {
														e.stopPropagation();
														skipBackward();
													}}
													className="w-9 h-9 text-muted-foreground hover:text-primary transition-colors"
													title="Rewind 10 seconds"
													disabled={!duration}
												>
													<SkipBack className="w-5 h-5" />
												</Button>
											</motion.div>
											<motion.div whileHover={{ scale: 1.2 }} whileTap={{ scale: 0.95 }}>
												<Button
													variant="ghost"
													size="icon"
													onClick={(e) => {
														e.stopPropagation();
														togglePlayPause();
													}}
													className="w-10 h-10 text-primary hover:bg-primary/10 rounded-full transition-colors"
													disabled={!duration}
												>
													{isPlaying ? (
														<Pause className="w-6 h-6" />
													) : (
														<Play className="w-6 h-6 ml-0.5" />
													)}
												</Button>
											</motion.div>
											<motion.div whileHover={{ scale: 1.2 }} whileTap={{ scale: 0.95 }}>
												<Button
													variant="ghost"
													size="icon"
													onClick={(e) => {
														e.stopPropagation();
														skipForward();
													}}
													className="w-9 h-9 text-muted-foreground hover:text-primary transition-colors"
													title="Forward 10 seconds"
													disabled={!duration}
												>
													<SkipForward className="w-5 h-5" />
												</Button>
											</motion.div>
										</motion.div>
									)}

									<div className="absolute top-2 right-2 z-20">
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button
													variant="ghost"
													size="icon"
													className="h-7 w-7 bg-background/50 hover:bg-background/80 rounded-full backdrop-blur-sm"
													onClick={(e) => e.stopPropagation()}
												>
													<MoreHorizontal className="h-4 w-4" />
													<span className="sr-only">Open menu</span>
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end">
												<DropdownMenuItem
													className="text-destructive focus:text-destructive"
													onClick={(e) => {
														e.stopPropagation();
														setPodcastToDelete({
															id: podcast.id,
															title: podcast.title,
														});
														setDeleteDialogOpen(true);
													}}
												>
													<Trash2 className="mr-2 h-4 w-4" />
													<span>Delete Podcast</span>
												</DropdownMenuItem>
											</DropdownMenuContent>
										</DropdownMenu>
									</div>
								</MotionCard>
							))}
						</motion.div>
					</AnimatePresence>
				)}

				{/* Current Podcast Player (Fixed at bottom) */}
				{currentPodcast && !isAudioLoading && audioSrc && (
					<motion.div
						initial={{ y: 100, opacity: 0 }}
						animate={{ y: 0, opacity: 1 }}
						exit={{ y: 100, opacity: 0 }}
						transition={{ type: "spring", stiffness: 300, damping: 30 }}
						className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-sm border-t p-4 shadow-lg z-50"
					>
						<div className="container mx-auto">
							<div className="flex flex-col md:flex-row items-center gap-4">
								<div className="flex-shrink-0">
									<motion.div
										className="w-12 h-12 bg-primary/20 rounded-md flex items-center justify-center"
										animate={{ scale: isPlaying ? [1, 1.05, 1] : 1 }}
										transition={{
											repeat: isPlaying ? Infinity : 0,
											duration: 2,
										}}
									>
										<Podcast className="h-6 w-6 text-primary" />
									</motion.div>
								</div>

								<div className="flex-grow min-w-0">
									<h4 className="font-medium text-sm line-clamp-1">{currentPodcast.title}</h4>

									<div className="flex items-center gap-2 mt-2">
										<div className="flex-grow relative">
											<Slider
												value={[currentTime]}
												min={0}
												max={duration || 100}
												step={0.1}
												onValueChange={handleSeek}
												className="relative z-10"
											/>
											<motion.div
												className="absolute left-0 top-1/2 h-2 bg-primary/25 rounded-full -translate-y-1/2"
												style={{
													width: `${(currentTime / (duration || 100)) * 100}%`,
												}}
												transition={{ ease: "linear" }}
											/>
										</div>
										<div className="flex-shrink-0 text-xs text-muted-foreground whitespace-nowrap">
											{formatTime(currentTime)} / {formatTime(duration)}
										</div>
									</div>
								</div>

								<div className="flex items-center gap-2">
									<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
										<Button variant="ghost" size="icon" onClick={skipBackward} className="h-8 w-8">
											<SkipBack className="h-4 w-4" />
										</Button>
									</motion.div>

									<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
										<Button
											variant="default"
											size="icon"
											onClick={togglePlayPause}
											className="h-10 w-10 rounded-full"
										>
											{isPlaying ? (
												<Pause className="h-5 w-5" />
											) : (
												<Play className="h-5 w-5 ml-0.5" />
											)}
										</Button>
									</motion.div>

									<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
										<Button variant="ghost" size="icon" onClick={skipForward} className="h-8 w-8">
											<SkipForward className="h-4 w-4" />
										</Button>
									</motion.div>

									<div className="hidden md:flex items-center gap-2 ml-4 w-32">
										<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
											<Button
												variant="ghost"
												size="icon"
												onClick={toggleMute}
												className={`h-8 w-8 ${isMuted ? "text-muted-foreground" : "text-primary"}`}
											>
												{isMuted ? (
													<VolumeX className="h-4 w-4" />
												) : (
													<Volume2 className="h-4 w-4" />
												)}
											</Button>
										</motion.div>

										<div className="relative w-full">
											<Slider
												value={[isMuted ? 0 : volume]}
												min={0}
												max={1}
												step={0.01}
												onValueChange={handleVolumeChange}
												className="w-full"
												disabled={isMuted}
											/>
											<motion.div
												className={`absolute left-0 bottom-0 h-1 bg-primary/30 rounded-full ${isMuted ? "opacity-50" : ""}`}
												initial={false}
												animate={{ width: `${(isMuted ? 0 : volume) * 100}%` }}
											/>
										</div>
									</div>

									<motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
										<Button
											variant="default"
											size="icon"
											onClick={closePlayer}
											className="h-10 w-10 rounded-full"
										>
											<X />
										</Button>
									</motion.div>
								</div>
							</div>
						</div>
					</motion.div>
				)}
			</div>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>Delete Podcast</span>
						</DialogTitle>
						<DialogDescription>
							Are you sure you want to delete{" "}
							<span className="font-medium">{podcastToDelete?.title}</span>? This action cannot be
							undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex gap-2 sm:justify-end">
						<Button
							variant="outline"
							onClick={() => setDeleteDialogOpen(false)}
							disabled={isDeleting}
						>
							Cancel
						</Button>
						<Button
							variant="destructive"
							onClick={handleDeletePodcast}
							disabled={isDeleting}
							className="gap-2"
						>
							{isDeleting ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									Deleting...
								</>
							) : (
								<>
									<Trash2 className="h-4 w-4" />
									Delete
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Hidden audio element for playback */}
			<audio
				ref={audioRef}
				src={audioSrc}
				preload="auto"
				onTimeUpdate={handleTimeUpdate}
				onLoadedMetadata={handleMetadataLoaded}
				onLoadedData={() => {
					// Only auto-play when audio is fully loaded
					if (audioRef.current && currentPodcast && audioSrc) {
						// Small delay to ensure browser is ready to play
						setTimeout(() => {
							if (audioRef.current) {
								audioRef.current
									.play()
									.then(() => {
										setIsPlaying(true);
									})
									.catch((error) => {
										console.error("Error playing audio:", error);
										// Don't show error if it's just the user navigating away
										if (error.name !== "AbortError") {
											toast.error("Failed to play audio.");
										}
										setIsPlaying(false);
									});
							}
						}, 100);
					}
				}}
				onEnded={() => setIsPlaying(false)}
				onError={(e) => {
					console.error("Audio error:", e);
					if (audioRef.current?.error) {
						// Log the specific error code for debugging
						console.error("Audio error code:", audioRef.current.error.code);

						// Don't show error message for aborted loads
						if (audioRef.current.error.code !== audioRef.current.error.MEDIA_ERR_ABORTED) {
							toast.error("Error playing audio. Please try again.");
						}
					}
					// Reset playing state on error
					setIsPlaying(false);
				}}
			>
				<track kind="captions" />
			</audio>
		</motion.div>
	);
}
