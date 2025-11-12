"use client";

import { format } from "date-fns";
import {
  Calendar,
  ExternalLink,
  MessageCircleMore,
  MoreHorizontal,
  Search,
  Tag,
  Trash2,
} from "lucide-react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
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
import { useAtom, useAtomValue } from "jotai";
import { activeSearchSpaceChatsAtom } from "@/atoms/chats/queries/active-search-space-chats.query.atom";
import { deleteChatMutationAtom } from "@/atoms/chats/mutations/delete-chat.mutation.atom";

export interface Chat {
  created_at: string;
  id: number;
  type: "DOCUMENT" | "CHAT";
  title: string;
  search_space_id: number;
  state_version: number;
}

export interface ChatDetails {
  type: "DOCUMENT" | "CHAT";
  title: string;
  initial_connectors: string[];
  messages: any[];
  created_at: string;
  id: number;
  search_space_id: number;
  state_version: number;
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

export default function ChatsPageClient({
  searchSpaceId,
}: ChatsPageClientProps) {
  const router = useRouter();
  const [filteredChats, setFilteredChats] = useState<Chat[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [sortOrder, setSortOrder] = useState<string>("newest");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<{
    id: number;
    title: string;
  } | null>(null);
  const {
    isFetching: isFetchingChats,
    data: chats,
    error: fetchError,
  } = useAtomValue(activeSearchSpaceChatsAtom);
  const [
    { isPending: isDeletingChat, mutateAsync: deleteChat, error: deleteError }
  ] = useAtom(deleteChatMutationAtom);

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

  useEffect(() => {
    if (fetchError) {
      console.error("Error fetching chats:", fetchError);
    }
  }, [fetchError]);

  useEffect(() => {
    if (deleteError) {
      console.error("Error deleting chat:", deleteError);
    }
  }, [deleteError]);

  // Filter and sort chats based on search query, type, and sort order
  useEffect(() => {
    let result = [...(chats || [])];

    // Filter by search term
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((chat) =>
        chat.title.toLowerCase().includes(query)
      );
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
    if (
      currentPage !== 1 &&
      (searchQuery || selectedType !== "all" || sortOrder !== "newest")
    ) {
      setCurrentPage(1);
    }
  }, [chats, searchQuery, selectedType, sortOrder, currentPage]);

  // Function to handle chat deletion
  const handleDeleteChat = async () => {
    if (!chatToDelete) return;

    await deleteChat(chatToDelete.id);

    setDeleteDialogOpen(false);
    setChatToDelete(null);
  };

  // Calculate pagination
  const indexOfLastChat = currentPage * chatsPerPage; // Index of last chat in the current page
  const indexOfFirstChat = indexOfLastChat - chatsPerPage; // Index of first chat in the current page
  const currentChats = filteredChats.slice(indexOfFirstChat, indexOfLastChat);

  // Get unique chat types for filter dropdown
  const chatTypes = chats
    ? ["all", ...Array.from(new Set(chats.map((chat) => chat.type)))]
    : [];

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
          <p className="text-muted-foreground">
            View, search, and manage all your chats.
          </p>
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
                      {type === "all"
                        ? "All Types"
                        : type.charAt(0).toUpperCase() + type.slice(1)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
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
        {isFetchingChats && (
          <div className="flex items-center justify-center h-40">
            <div className="flex flex-col items-center gap-2">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
              <p className="text-sm text-muted-foreground">Loading chats...</p>
            </div>
          </div>
        )}

        {fetchError && !isFetchingChats && (
          <div className="border border-destructive/50 text-destructive p-4 rounded-md">
            <h3 className="font-medium">Error loading chats</h3>
            <p className="text-sm">{fetchError.message}</p>
          </div>
        )}

        {!isFetchingChats && !fetchError && filteredChats.length === 0 && (
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
        {!isFetchingChats && !fetchError && filteredChats.length > 0 && (
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
                  className="overflow-hidden hover:shadow-md transition-shadow"
                >
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="line-clamp-1">
                          {chat.title || `Chat ${chat.id}`}
                        </CardTitle>
                        <CardDescription>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3.5 w-3.5" />
                            <span>
                              {format(new Date(chat.created_at), "MMM d, yyyy")}
                            </span>
                          </span>
                        </CardDescription>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
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
                        router.push(
                          `/dashboard/${chat.search_space_id}/researcher/${chat.id}`
                        )
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
        {!isFetchingChats && !fetchError && totalPages > 1 && (
          <Pagination className="mt-8">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href={`?page=${Math.max(1, currentPage - 1)}`}
                  onClick={(e) => {
                    e.preventDefault();
                    if (currentPage > 1) setCurrentPage(currentPage - 1);
                  }}
                  className={
                    currentPage <= 1 ? "pointer-events-none opacity-50" : ""
                  }
                />
              </PaginationItem>

              {Array.from({ length: totalPages }).map((_, index) => {
                const pageNumber = index + 1;
                const isVisible =
                  pageNumber === 1 ||
                  pageNumber === totalPages ||
                  (pageNumber >= currentPage - 1 &&
                    pageNumber <= currentPage + 1);

                if (!isVisible) {
                  // Show ellipsis at appropriate positions
                  if (pageNumber === 2 || pageNumber === totalPages - 1) {
                    return (
                      <PaginationItem key={pageNumber}>
                        <span className="flex h-9 w-9 items-center justify-center">
                          ...
                        </span>
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
                    if (currentPage < totalPages)
                      setCurrentPage(currentPage + 1);
                  }}
                  className={
                    currentPage >= totalPages
                      ? "pointer-events-none opacity-50"
                      : ""
                  }
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
              <span className="font-medium">{chatToDelete?.title}</span>? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2 sm:justify-end">
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeletingChat}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteChat}
              disabled={isDeletingChat}
              className="gap-2"
            >
              {isDeletingChat ? (
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
    </motion.div>
  );
}
