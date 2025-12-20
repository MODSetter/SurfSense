"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { Loader2, MessageCircleMore, MoreHorizontal, Search, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { cn } from "@/lib/utils";

interface AllChatsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
}

export function AllChatsSidebar({ open, onOpenChange, searchSpaceId }: AllChatsSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const queryClient = useQueryClient();
	const [deletingChatId, setDeletingChatId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	const isSearchMode = !!debouncedSearchQuery.trim();

	// Fetch all chats (when not searching)
	const {
		data: chatsData,
		error: chatsError,
		isLoading: isLoadingChats,
	} = useQuery({
		queryKey: ["all-chats", searchSpaceId],
		queryFn: () =>
			chatsApiService.getChats({
				queryParams: {
					search_space_id: Number(searchSpaceId),
				},
			}),
		enabled: !!searchSpaceId && open && !isSearchMode,
	});

	// Search chats (when searching)
	const {
		data: searchData,
		error: searchError,
		isLoading: isLoadingSearch,
	} = useQuery({
		queryKey: ["search-chats", searchSpaceId, debouncedSearchQuery],
		queryFn: () =>
			chatsApiService.searchChats({
				queryParams: {
					title: debouncedSearchQuery.trim(),
					search_space_id: Number(searchSpaceId),
				},
			}),
		enabled: !!searchSpaceId && open && isSearchMode,
	});

	// Handle chat navigation
	const handleChatClick = useCallback(
		(chatId: number, chatSearchSpaceId: number) => {
			router.push(`/dashboard/${chatSearchSpaceId}/researcher/${chatId}`);
			onOpenChange(false);
		},
		[router, onOpenChange]
	);

	// Handle chat deletion
	const handleDeleteChat = useCallback(
		async (chatId: number) => {
			setDeletingChatId(chatId);
			try {
				await chatsApiService.deleteChat({ id: chatId });
				toast.success(t("chat_deleted") || "Chat deleted successfully");
				// Invalidate queries to refresh the list
				queryClient.invalidateQueries({ queryKey: ["all-chats", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["search-chats", searchSpaceId] });
				queryClient.invalidateQueries({ queryKey: ["chats"] });
			} catch (error) {
				console.error("Error deleting chat:", error);
				toast.error(t("error_deleting_chat") || "Failed to delete chat");
			} finally {
				setDeletingChatId(null);
			}
		},
		[queryClient, searchSpaceId, t]
	);

	// Clear search
	const handleClearSearch = useCallback(() => {
		setSearchQuery("");
	}, []);

	// Determine which data source to use and loading/error states
	const chats = isSearchMode ? (searchData ?? []) : (chatsData ?? []);
	const isLoading = isSearchMode ? isLoadingSearch : isLoadingChats;
	const error = isSearchMode ? searchError : chatsError;

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="left" className="w-80 p-0 flex flex-col">
				<SheetHeader className="mx-3 px-4 py-4 border-b space-y-3">
					<SheetTitle>{t("all_chats") || "All Chats"}</SheetTitle>
					<SheetDescription className="sr-only">
						{t("all_chats_description") || "Browse and manage all your chats"}
					</SheetDescription>

					{/* Search Input */}
					<div className="relative">
						<Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
						<Input
							type="text"
							placeholder={t("search_chats") || "Search chats..."}
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							className="pl-9 pr-8 h-9"
						/>
						{searchQuery && (
							<Button
								variant="ghost"
								size="icon"
								className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
								onClick={handleClearSearch}
							>
								<X className="h-3.5 w-3.5" />
								<span className="sr-only">{t("clear_search") || "Clear search"}</span>
							</Button>
						)}
					</div>
				</SheetHeader>

				<ScrollArea className="flex-1">
					<div className="p-2">
						{isLoading ? (
							<div className="flex items-center justify-center py-8">
								<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
							</div>
						) : error ? (
							<div className="text-center py-8 text-sm text-destructive">
								{t("error_loading_chats") || "Error loading chats"}
							</div>
						) : chats.length > 0 ? (
							<div className="space-y-1">
								{chats.map((chat) => {
									const isDeleting = deletingChatId === chat.id;

									return (
										<div
											key={chat.id}
											className={cn(
												"group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
												"hover:bg-accent hover:text-accent-foreground",
												"transition-colors cursor-pointer",
												isDeleting && "opacity-50 pointer-events-none"
											)}
										>
											{/* Main clickable area for navigation */}
											<Tooltip>
												<TooltipTrigger asChild>
													<button
														type="button"
														onClick={() => handleChatClick(chat.id, chat.search_space_id)}
														disabled={isDeleting}
														className="flex items-center gap-2 flex-1 min-w-0 text-left"
													>
														<MessageCircleMore className="h-4 w-4 shrink-0 text-muted-foreground" />
														<span className="truncate">{chat.title}</span>
													</button>
												</TooltipTrigger>
												<TooltipContent side="right">
													<p>
														{t("created") || "Created"}:{" "}
														{format(new Date(chat.created_at), "MMM d, yyyy 'at' h:mm a")}
													</p>
												</TooltipContent>
											</Tooltip>

											{/* Actions dropdown - separate from main click area */}
											<DropdownMenu>
												<DropdownMenuTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className={cn(
															"h-6 w-6 shrink-0",
															"opacity-0 group-hover:opacity-100 focus:opacity-100",
															"transition-opacity"
														)}
														disabled={isDeleting}
													>
														{isDeleting ? (
															<Loader2 className="h-3.5 w-3.5 animate-spin" />
														) : (
															<MoreHorizontal className="h-3.5 w-3.5" />
														)}
														<span className="sr-only">{t("more_options") || "More options"}</span>
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end" className="w-40">
													<DropdownMenuItem
														onClick={() => handleDeleteChat(chat.id)}
														className="text-destructive focus:text-destructive"
													>
														<Trash2 className="mr-2 h-4 w-4" />
														<span>{t("delete") || "Delete"}</span>
													</DropdownMenuItem>
												</DropdownMenuContent>
											</DropdownMenu>
										</div>
									);
								})}
							</div>
						) : isSearchMode ? (
							<div className="text-center py-8">
								<Search className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
								<p className="text-sm text-muted-foreground">
									{t("no_chats_found") || "No chats found"}
								</p>
								<p className="text-xs text-muted-foreground/70 mt-1">
									{t("try_different_search") || "Try a different search term"}
								</p>
							</div>
						) : (
							<div className="text-center py-8">
								<MessageCircleMore className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
								<p className="text-sm text-muted-foreground">{t("no_chats") || "No chats yet"}</p>
								<p className="text-xs text-muted-foreground/70 mt-1">
									{t("start_new_chat_hint") || "Start a new chat from the researcher"}
								</p>
							</div>
						)}
					</div>
				</ScrollArea>
			</SheetContent>
		</Sheet>
	);
}
