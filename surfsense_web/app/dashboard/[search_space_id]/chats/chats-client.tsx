"use client";

import { format } from "date-fns";
import {
	Calendar,
	CheckCircle,
	Circle,
	ExternalLink,
	MessageCircleMore,
	MoreHorizontal,
	Podcast,
	Search,
	Tag,
	Trash2,
} from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
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
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
// UI Components
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationLink,
	PaginationNext,
	PaginationPrevious,
} from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface Chat {
	created_at: string;
	id: number;
	type: string;
	title: string;
	search_space_id: number;
}

interface ChatsPageClientProps {
	searchSpaceId: string;
}

const pageVariants: Variants = {
	initial: { opacity: 0 },
	enter: { opacity: 1, transition: { duration: 0.3, ease: "easeInOut" } },
	exit: { opacity: 0, transition: { duration: 0.3, ease: "easeInOut" } },
};

const chatCardVariants: Variants = {
	initial: { y: 20, opacity: 0 },
	animate: { y: 0, opacity: 1 },
	exit: { y: -20, opacity: 0 },
};

const MotionCard = motion(Card);

export default function ChatsPageClient({ searchSpaceId }: ChatsPageClientProps) {
	const router = useRouter();
	const [chats, setChats] = useState<Chat[]>([]);
	const [filteredChats, setFilteredChats] = useState<Chat[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [currentPage, setCurrentPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [selectedType, setSelectedType] = useState<string>("all");
	const [sortOrder, setSortOrder] = useState<string>("newest");
	const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
	const [chatToDelete, setChatToDelete] = useState<{ id: number; title: string } | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);

	// New state for podcast generation
	const [selectedChats, setSelectedChats] = useState<number[]>([]);
	const [selectionMode, setSelectionMode] = useState(false);
	const [podcastDialogOpen, setPodcastDialogOpen] = useState(false);
	const [podcastTitle, setPodcastTitle] = useState("");
	const [isGeneratingPodcast, setIsGeneratingPodcast] = useState(false);

	// New state for individual podcast generation
	const [currentChatIndex, setCurrentChatIndex] = useState(0);
	const [podcastTitles, setPodcastTitles] = useState<{ [key: number]: string }>({});
	const [processingChat, setProcessingChat] = useState<Chat | null>(null);

	const chatsPerPage = 9;
	const searchParams = useSearchParams();

	// Get initial page from URL params if it exists
	useEffect(() => {
		const pageParam = searchParams.get("page");
		if (pageParam) {
			const pageNumber = parseInt(pageParam, 10);
			if (!Number.isNaN(pageNumber) && pageNumber > 0) {
				setCurrentPage(pageNumber);
			}
		}
	}, [searchParams]);

	// Fetch chats from API
	useEffect(() => {
		const fetchChats = async () => {
			try {
				setIsLoading(true);

				// Get token from localStorage
				const token = localStorage.getItem("surfsense_bearer_token");

				if (!token) {
					setError("Authentication token not found. Please log in again.");
					setIsLoading(false);
					return;
				}

				// Fetch all chats for this search space
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats?search_space_id=${searchSpaceId}`,
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
					throw new Error(`Failed to fetch chats: ${response.status} ${errorData?.error || ""}`);
				}

				const data: Chat[] = await response.json();
				setChats(data);
				setFilteredChats(data);
				setError(null);
			} catch (error) {
				console.error("Error fetching chats:", error);
				setError(error instanceof Error ? error.message : "Unknown error occurred");
				setChats([]);
				setFilteredChats([]);
			} finally {
				setIsLoading(false);
			}
		};

		fetchChats();
	}, [searchSpaceId]);

	// Filter and sort chats based on search query, type, and sort order
	useEffect(() => {
		let result = [...chats];

		// Filter by search term
		if (searchQuery) {
			const query = searchQuery.toLowerCase();
			result = result.filter((chat) => chat.title.toLowerCase().includes(query));
		}

		// Filter by type
		if (selectedType !== "all") {
			result = result.filter((chat) => chat.type === selectedType);
		}

		// Sort chats
		result.sort((a, b) => {
			const dateA = new Date(a.created_at).getTime();
			const dateB = new Date(b.created_at).getTime();

			return sortOrder === "newest" ? dateB - dateA : dateA - dateB;
		});

		setFilteredChats(result);
		setTotalPages(Math.max(1, Math.ceil(result.length / chatsPerPage)));

		// Reset to first page when filters change
		if (currentPage !== 1 && (searchQuery || selectedType !== "all" || sortOrder !== "newest")) {
			setCurrentPage(1);
		}
	}, [chats, searchQuery, selectedType, sortOrder, currentPage]);

	// Function to handle chat deletion
	const handleDeleteChat = async () => {
		if (!chatToDelete) return;

		setIsDeleting(true);
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				setIsDeleting(false);
				return;
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${chatToDelete.id}`,
				{
					method: "DELETE",
					headers: {
						Authorization: `Bearer ${token}`,
						"Content-Type": "application/json",
					},
				}
			);

			if (!response.ok) {
				throw new Error(`Failed to delete chat: ${response.statusText}`);
			}

			// Close dialog and refresh chats
			setDeleteDialogOpen(false);
			setChatToDelete(null);

			// Update local state by removing the deleted chat
			setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatToDelete.id));
		} catch (error) {
			console.error("Error deleting chat:", error);
		} finally {
			setIsDeleting(false);
		}
	};

	// Calculate pagination
	const indexOfLastChat = currentPage * chatsPerPage;
	const indexOfFirstChat = indexOfLastChat - chatsPerPage;
	const currentChats = filteredChats.slice(indexOfFirstChat, indexOfLastChat);

	// Get unique chat types for filter dropdown
	const chatTypes = ["all", ...Array.from(new Set(chats.map((chat) => chat.type)))];

	// Generate individual podcasts from selected chats
	const handleGeneratePodcast = async () => {
		if (selectedChats.length === 0) {
			toast.error("Please select at least one chat");
			return;
		}

		const currentChatId = selectedChats[currentChatIndex];
		const currentTitle = podcastTitles[currentChatId] || podcastTitle;

		if (!currentTitle.trim()) {
			toast.error("Please enter a podcast title");
			return;
		}

		setIsGeneratingPodcast(true);
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				toast.error("Authentication error. Please log in again.");
				setIsGeneratingPodcast(false);
				return;
			}

			// Create payload for single chat
			const payload = {
				type: "CHAT",
				ids: [currentChatId], // Single chat ID
				search_space_id: parseInt(searchSpaceId),
				podcast_title: currentTitle,
			};

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/generate`,
				{
					method: "POST",
					headers: {
						Authorization: `Bearer ${token}`,
						"Content-Type": "application/json",
					},
					body: JSON.stringify(payload),
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to generate podcast");
			}

			const _data = await response.json();
			toast.success(`Podcast "${currentTitle}" generation started!`);

			// Move to the next chat or finish
			if (currentChatIndex < selectedChats.length - 1) {
				// Set up for next chat
				setCurrentChatIndex(currentChatIndex + 1);

				// Find the next chat from the chats array
				const nextChatId = selectedChats[currentChatIndex + 1];
				const nextChat = chats.find((chat) => chat.id === nextChatId) || null;
				setProcessingChat(nextChat);

				// Default title for the next chat
				if (!podcastTitles[nextChatId]) {
					setPodcastTitle(nextChat?.title || `Podcast from Chat ${nextChatId}`);
				} else {
					setPodcastTitle(podcastTitles[nextChatId]);
				}

				setIsGeneratingPodcast(false);
			} else {
				// All done
				finishPodcastGeneration();
			}
		} catch (error) {
			console.error("Error generating podcast:", error);
			toast.error(error instanceof Error ? error.message : "Failed to generate podcast");
			setIsGeneratingPodcast(false);
		}
	};

	// Helper to finish the podcast generation process
	const finishPodcastGeneration = () => {
		toast.success("All podcasts are being generated! Check the logs tab to see their status.");
		setPodcastDialogOpen(false);
		setSelectedChats([]);
		setSelectionMode(false);
		setCurrentChatIndex(0);
		setPodcastTitles({});
		setProcessingChat(null);
		setPodcastTitle("");
		setIsGeneratingPodcast(false);
	};

	// Start podcast generation flow
	const startPodcastGeneration = () => {
		if (selectedChats.length === 0) {
			toast.error("Please select at least one chat");
			return;
		}

		// Reset the state for podcast generation
		setCurrentChatIndex(0);
		setPodcastTitles({});

		// Set up for the first chat
		const firstChatId = selectedChats[0];
		const firstChat = chats.find((chat) => chat.id === firstChatId) || null;
		setProcessingChat(firstChat);

		// Set default title for the first chat
		setPodcastTitle(firstChat?.title || `Podcast from Chat ${firstChatId}`);
		setPodcastDialogOpen(true);
	};

	// Update the title for the current chat
	const updateCurrentChatTitle = (title: string) => {
		const currentChatId = selectedChats[currentChatIndex];
		setPodcastTitle(title);
		setPodcastTitles((prev) => ({
			...prev,
			[currentChatId]: title,
		}));
	};

	// Skip generating a podcast for the current chat
	const skipCurrentChat = () => {
		if (currentChatIndex < selectedChats.length - 1) {
			// Move to the next chat
			setCurrentChatIndex(currentChatIndex + 1);

			// Find the next chat
			const nextChatId = selectedChats[currentChatIndex + 1];
			const nextChat = chats.find((chat) => chat.id === nextChatId) || null;
			setProcessingChat(nextChat);

			// Set default title for the next chat
			if (!podcastTitles[nextChatId]) {
				setPodcastTitle(nextChat?.title || `Podcast from Chat ${nextChatId}`);
			} else {
				setPodcastTitle(podcastTitles[nextChatId]);
			}
		} else {
			// All done (all skipped)
			finishPodcastGeneration();
		}
	};

	// Toggle chat selection
	const toggleChatSelection = (chatId: number) => {
		setSelectedChats((prev) =>
			prev.includes(chatId) ? prev.filter((id) => id !== chatId) : [...prev, chatId]
		);
	};

	// Select all visible chats
	const selectAllVisibleChats = () => {
		const visibleChatIds = currentChats.map((chat) => chat.id);
		setSelectedChats((prev) => {
			const allSelected = visibleChatIds.every((id) => prev.includes(id));
			return allSelected
				? prev.filter((id) => !visibleChatIds.includes(id)) // Deselect all visible if all are selected
				: [...new Set([...prev, ...visibleChatIds])]; // Add all visible, ensuring no duplicates
		});
	};

	// Cancel selection mode
	const cancelSelectionMode = () => {
		setSelectionMode(false);
		setSelectedChats([]);
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
					<h1 className="text-3xl font-bold tracking-tight">All Chats</h1>
					<p className="text-muted-foreground">View, search, and manage all your chats.</p>
				</div>

				{/* Filter and Search Bar */}
				<div className="flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0">
					<div className="flex flex-1 items-center gap-2">
						<div className="relative w-full md:w-80">
							<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
							<Input
								type="text"
								placeholder="Search chats..."
								className="pl-8"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
							/>
						</div>

						<Select value={selectedType} onValueChange={setSelectedType}>
							<SelectTrigger className="w-full md:w-40">
								<SelectValue placeholder="Filter by type" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									{chatTypes.map((type) => (
										<SelectItem key={type} value={type}>
											{type === "all" ? "All Types" : type.charAt(0).toUpperCase() + type.slice(1)}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					</div>

					<div className="flex items-center gap-2">
						{selectionMode ? (
							<>
								<Button
									variant="outline"
									size="sm"
									onClick={selectAllVisibleChats}
									className="gap-1"
									title="Select or deselect all chats on the current page"
								>
									<CheckCircle className="h-4 w-4" />
									{currentChats.every((chat) => selectedChats.includes(chat.id))
										? "Deselect Page"
										: "Select Page"}
								</Button>
								<Button
									variant="default"
									size="sm"
									onClick={startPodcastGeneration}
									className="gap-1"
									disabled={selectedChats.length === 0}
								>
									<Podcast className="h-4 w-4" />
									Generate Podcast ({selectedChats.length})
								</Button>
								<Button variant="ghost" size="sm" onClick={cancelSelectionMode}>
									Cancel
								</Button>
							</>
						) : (
							<>
								<Button
									variant="outline"
									size="sm"
									onClick={() => setSelectionMode(true)}
									className="gap-1"
								>
									<Podcast className="h-4 w-4" />
									Podcaster
								</Button>
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
							</>
						)}
					</div>
				</div>

				{/* Status Messages */}
				{isLoading && (
					<div className="flex items-center justify-center h-40">
						<div className="flex flex-col items-center gap-2">
							<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
							<p className="text-sm text-muted-foreground">Loading chats...</p>
						</div>
					</div>
				)}

				{error && !isLoading && (
					<div className="border border-destructive/50 text-destructive p-4 rounded-md">
						<h3 className="font-medium">Error loading chats</h3>
						<p className="text-sm">{error}</p>
					</div>
				)}

				{!isLoading && !error && filteredChats.length === 0 && (
					<div className="flex flex-col items-center justify-center h-40 gap-2 text-center">
						<MessageCircleMore className="h-8 w-8 text-muted-foreground" />
						<h3 className="font-medium">No chats found</h3>
						<p className="text-sm text-muted-foreground">
							{searchQuery || selectedType !== "all"
								? "Try adjusting your search filters"
								: "Start a new chat to get started"}
						</p>
					</div>
				)}

				{/* Chat Grid */}
				{!isLoading && !error && filteredChats.length > 0 && (
					<AnimatePresence mode="wait">
						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
							{currentChats.map((chat, index) => (
								<MotionCard
									key={chat.id}
									variants={chatCardVariants}
									initial="initial"
									animate="animate"
									exit="exit"
									transition={{ duration: 0.2, delay: index * 0.05 }}
									className={cn(
										"overflow-hidden hover:shadow-md transition-shadow",
										selectionMode && selectedChats.includes(chat.id)
											? "ring-2 ring-primary ring-offset-2"
											: ""
									)}
									onClick={(e) => {
										if (!selectionMode) return;
										// Ignore clicks coming from interactive elements
										if ((e.target as HTMLElement).closest("button, a, [data-stop-selection]"))
											return;
										toggleChatSelection(chat.id);
									}}
								>
									<CardHeader className="pb-3">
										<div className="flex justify-between items-start">
											<div className="space-y-1 flex items-start gap-2">
												{selectionMode && (
													<div className="mt-1">
														{selectedChats.includes(chat.id) ? (
															<CheckCircle className="h-4 w-4 text-primary" />
														) : (
															<Circle className="h-4 w-4 text-muted-foreground" />
														)}
													</div>
												)}
												<div>
													<CardTitle className="line-clamp-1">
														{chat.title || `Chat ${chat.id}`}
													</CardTitle>
													<CardDescription>
														<span className="flex items-center gap-1">
															<Calendar className="h-3.5 w-3.5" />
															<span>{format(new Date(chat.created_at), "MMM d, yyyy")}</span>
														</span>
													</CardDescription>
												</div>
											</div>
											{!selectionMode && (
												<DropdownMenu>
													<DropdownMenuTrigger asChild>
														<Button
															variant="ghost"
															size="icon"
															className="h-8 w-8"
															data-stop-selection
														>
															<MoreHorizontal className="h-4 w-4" />
															<span className="sr-only">Open menu</span>
														</Button>
													</DropdownMenuTrigger>
													<DropdownMenuContent align="end">
														<DropdownMenuItem
															onClick={() =>
																router.push(
																	`/dashboard/${chat.search_space_id}/researcher/${chat.id}`
																)
															}
														>
															<ExternalLink className="mr-2 h-4 w-4" />
															<span>View Chat</span>
														</DropdownMenuItem>
														<DropdownMenuItem
															onClick={() => {
																setSelectedChats([chat.id]);
																setPodcastTitle(chat.title || `Chat ${chat.id}`);
																setPodcastDialogOpen(true);
															}}
														>
															<Podcast className="mr-2 h-4 w-4" />
															<span>Generate Podcast</span>
														</DropdownMenuItem>
														<DropdownMenuSeparator />
														<DropdownMenuItem
															className="text-destructive focus:text-destructive"
															onClick={(e) => {
																e.stopPropagation();
																setChatToDelete({
																	id: chat.id,
																	title: chat.title || `Chat ${chat.id}`,
																});
																setDeleteDialogOpen(true);
															}}
														>
															<Trash2 className="mr-2 h-4 w-4" />
															<span>Delete Chat</span>
														</DropdownMenuItem>
													</DropdownMenuContent>
												</DropdownMenu>
											)}
										</div>
									</CardHeader>

									<CardFooter className="flex items-center justify-between gap-2 w-full">
										<Badge variant="secondary" className="text-xs">
											<Tag className="mr-1 h-3 w-3" />
											{chat.type || "Unknown"}
										</Badge>
										<Button
											size="sm"
											onClick={() =>
												router.push(`/dashboard/${chat.search_space_id}/researcher/${chat.id}`)
											}
										>
											<MessageCircleMore className="h-4 w-4" />
											<span>View Chat</span>
										</Button>
									</CardFooter>
								</MotionCard>
							))}
						</div>
					</AnimatePresence>
				)}

				{/* Pagination */}
				{!isLoading && !error && totalPages > 1 && (
					<Pagination className="mt-8">
						<PaginationContent>
							<PaginationItem>
								<PaginationPrevious
									href={`?page=${Math.max(1, currentPage - 1)}`}
									onClick={(e) => {
										e.preventDefault();
										if (currentPage > 1) setCurrentPage(currentPage - 1);
									}}
									className={currentPage <= 1 ? "pointer-events-none opacity-50" : ""}
								/>
							</PaginationItem>

							{Array.from({ length: totalPages }).map((_, index) => {
								const pageNumber = index + 1;
								const isVisible =
									pageNumber === 1 ||
									pageNumber === totalPages ||
									(pageNumber >= currentPage - 1 && pageNumber <= currentPage + 1);

								if (!isVisible) {
									// Show ellipsis at appropriate positions
									if (pageNumber === 2 || pageNumber === totalPages - 1) {
										return (
											<PaginationItem key={pageNumber}>
												<span className="flex h-9 w-9 items-center justify-center">...</span>
											</PaginationItem>
										);
									}
									return null;
								}

								return (
									<PaginationItem key={pageNumber}>
										<PaginationLink
											href={`?page=${pageNumber}`}
											onClick={(e) => {
												e.preventDefault();
												setCurrentPage(pageNumber);
											}}
											isActive={pageNumber === currentPage}
										>
											{pageNumber}
										</PaginationLink>
									</PaginationItem>
								);
							})}

							<PaginationItem>
								<PaginationNext
									href={`?page=${Math.min(totalPages, currentPage + 1)}`}
									onClick={(e) => {
										e.preventDefault();
										if (currentPage < totalPages) setCurrentPage(currentPage + 1);
									}}
									className={currentPage >= totalPages ? "pointer-events-none opacity-50" : ""}
								/>
							</PaginationItem>
						</PaginationContent>
					</Pagination>
				)}
			</div>

			{/* Delete Confirmation Dialog */}
			<Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Trash2 className="h-5 w-5 text-destructive" />
							<span>Delete Chat</span>
						</DialogTitle>
						<DialogDescription>
							Are you sure you want to delete{" "}
							<span className="font-medium">{chatToDelete?.title}</span>? This action cannot be
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
							onClick={handleDeleteChat}
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

			{/* Podcast Generation Dialog */}
			<Dialog
				open={podcastDialogOpen}
				onOpenChange={(isOpen: boolean) => {
					if (!isOpen) {
						// Cancel the process if dialog is closed
						setPodcastDialogOpen(false);
						setSelectedChats([]);
						setSelectionMode(false);
						setCurrentChatIndex(0);
						setPodcastTitles({});
						setProcessingChat(null);
						setPodcastTitle("");
					} else {
						setPodcastDialogOpen(true);
					}
				}}
			>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<Podcast className="h-5 w-5 text-primary" />
							<span>
								Generate Podcast {currentChatIndex + 1} of {selectedChats.length}
							</span>
						</DialogTitle>
						<DialogDescription>
							{selectedChats.length > 1 ? (
								<>
									Creating individual podcasts for each selected chat. Currently processing:{" "}
									<span className="font-medium">
										{processingChat?.title || `Chat ${selectedChats[currentChatIndex]}`}
									</span>
								</>
							) : (
								"Create a podcast from this chat. The podcast will be available in the podcasts section once generated."
							)}
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-4 py-2">
						<div className="space-y-2">
							<Label htmlFor="podcast-title">Podcast Title</Label>
							<Input
								id="podcast-title"
								placeholder="Enter podcast title"
								value={podcastTitle}
								onChange={(e) => updateCurrentChatTitle(e.target.value)}
							/>
						</div>

						{selectedChats.length > 1 && (
							<div className="w-full bg-muted rounded-full h-2.5 mt-4">
								<div
									className="bg-primary h-2.5 rounded-full transition-all duration-300"
									style={{ width: `${(currentChatIndex / selectedChats.length) * 100}%` }}
								></div>
							</div>
						)}
					</div>

					<DialogFooter className="flex gap-2 sm:justify-end">
						{selectedChats.length > 1 && !isGeneratingPodcast && (
							<Button variant="outline" onClick={skipCurrentChat} className="gap-1">
								Skip
							</Button>
						)}
						<Button
							variant="outline"
							onClick={() => {
								setPodcastDialogOpen(false);
								setCurrentChatIndex(0);
								setPodcastTitles({});
								setProcessingChat(null);
							}}
							disabled={isGeneratingPodcast}
						>
							Cancel
						</Button>
						<Button
							variant="default"
							onClick={handleGeneratePodcast}
							disabled={isGeneratingPodcast}
							className="gap-2"
						>
							{isGeneratingPodcast ? (
								<>
									<span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
									Generating...
								</>
							) : (
								<>
									<Podcast className="h-4 w-4" />
									Generate Podcast
								</>
							)}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</motion.div>
	);
}
