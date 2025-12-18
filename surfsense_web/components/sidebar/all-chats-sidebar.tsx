"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageCircleMore, MoreHorizontal, Search, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
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
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { chatsApiService } from "@/lib/apis/chats-api.service";
import { cn } from "@/lib/utils";

interface AllChatsSidebarProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaceId: string;
}

export function AllChatsSidebar({
	open,
	onOpenChange,
	searchSpaceId,
}: AllChatsSidebarProps) {
	const t = useTranslations("sidebar");
	const router = useRouter();
	const queryClient = useQueryClient();
	const [deletingChatId, setDeletingChatId] = useState<number | null>(null);
	const [searchQuery, setSearchQuery] = useState("");
	const debouncedSearchQuery = useDebouncedValue(searchQuery, 300);

	// Fetch all chats
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
		enabled: !!searchSpaceId && open,
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

	// Filter chats based on search query (client-side filtering)
	const chats = useMemo(() => {
		const allChats = chatsData ?? [];
		if (!debouncedSearchQuery) {
			return allChats;
		}
		const query = debouncedSearchQuery.toLowerCase();
		return allChats.filter((chat) => 
			chat.title.toLowerCase().includes(query)
		);
	}, [chatsData, debouncedSearchQuery]);

	const isSearchMode = !!debouncedSearchQuery;

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="left" className="w-80 p-0 flex flex-col">
				<SheetHeader className="px-4 py-4 border-b space-y-3">
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
								<span className="sr-only">Clear search</span>
							</Button>
						)}
					</div>
				</SheetHeader>

				<ScrollArea className="flex-1">
					<div className="p-2">
						{isLoadingChats ? (
							<div className="flex items-center justify-center py-8">
								<Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
							</div>
						) : chatsError ? (
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
											<button
												type="button"
												onClick={() => handleChatClick(chat.id, chat.search_space_id)}
												disabled={isDeleting}
												className="flex items-center gap-2 flex-1 min-w-0 text-left"
											>
												<MessageCircleMore className="h-4 w-4 shrink-0 text-muted-foreground" />
												<span className="truncate">{chat.title}</span>
											</button>

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
														<span className="sr-only">More options</span>
													</Button>
												</DropdownMenuTrigger>
												<DropdownMenuContent align="end" className="w-40">
													<DropdownMenuItem
														onClick={() => handleDeleteChat(chat.id)}
														className="text-destructive focus:text-destructive"
													>
														<Trash2 className="mr-2 h-4 w-4" />
														<span>Delete</span>
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
								<p className="text-sm text-muted-foreground">
									{t("no_chats") || "No chats yet"}
								</p>
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
