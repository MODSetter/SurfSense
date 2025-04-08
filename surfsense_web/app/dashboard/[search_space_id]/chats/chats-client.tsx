'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'next/navigation';
import { MessageCircleMore, Search, Calendar, Tag, Trash2, ExternalLink, MoreHorizontal } from 'lucide-react';
import { format } from 'date-fns';

// UI Components
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Chat {
  created_at: string;
  id: number;
  type: string;
  title: string;
  messages: ChatMessage[];
  search_space_id: number;
}

interface ChatMessage {
  id: string;
  createdAt: string;
  role: string;
  content: string;
  parts?: any;
}

interface ChatsPageClientProps {
  searchSpaceId: string;
}

const pageVariants = {
  initial: { opacity: 0 },
  enter: { opacity: 1, transition: { duration: 0.3, ease: 'easeInOut' } },
  exit: { opacity: 0, transition: { duration: 0.3, ease: 'easeInOut' } }
};

const chatCardVariants = {
  initial: { y: 20, opacity: 0 },
  animate: { y: 0, opacity: 1 },
  exit: { y: -20, opacity: 0 }
};

const MotionCard = motion(Card);

export default function ChatsPageClient({ searchSpaceId }: ChatsPageClientProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [filteredChats, setFilteredChats] = useState<Chat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [sortOrder, setSortOrder] = useState<string>('newest');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<{ id: number, title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  const chatsPerPage = 9;
  const searchParams = useSearchParams();
  
  // Get initial page from URL params if it exists
  useEffect(() => {
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const pageNumber = parseInt(pageParam, 10);
      if (!isNaN(pageNumber) && pageNumber > 0) {
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
        const token = localStorage.getItem('surfsense_bearer_token');
        
        if (!token) {
          setError('Authentication token not found. Please log in again.');
          setIsLoading(false);
          return;
        }

        // Fetch all chats for this search space
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/?search_space_id=${searchSpaceId}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            cache: 'no-store',
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          throw new Error(`Failed to fetch chats: ${response.status} ${errorData?.error || ''}`);
        }

        const data: Chat[] = await response.json();
        setChats(data);
        setFilteredChats(data);
        setError(null);
      } catch (error) {
        console.error('Error fetching chats:', error);
        setError(error instanceof Error ? error.message : 'Unknown error occurred');
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
      result = result.filter(chat => 
        chat.title.toLowerCase().includes(query)
      );
    }
    
    // Filter by type
    if (selectedType !== 'all') {
      result = result.filter(chat => chat.type === selectedType);
    }
    
    // Sort chats
    result.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    setFilteredChats(result);
    setTotalPages(Math.max(1, Math.ceil(result.length / chatsPerPage)));
    
    // Reset to first page when filters change
    if (currentPage !== 1 && (searchQuery || selectedType !== 'all' || sortOrder !== 'newest')) {
      setCurrentPage(1);
    }
  }, [chats, searchQuery, selectedType, sortOrder, currentPage]);

  // Function to handle chat deletion
  const handleDeleteChat = async () => {
    if (!chatToDelete) return;
    
    setIsDeleting(true);
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      if (!token) {
        setIsDeleting(false);
        return;
      }
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${chatToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete chat: ${response.statusText}`);
      }
      
      // Close dialog and refresh chats
      setDeleteDialogOpen(false);
      setChatToDelete(null);
      
      // Update local state by removing the deleted chat
      setChats(prevChats => prevChats.filter(chat => chat.id !== chatToDelete.id));
    } catch (error) {
      console.error('Error deleting chat:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  // Calculate pagination
  const indexOfLastChat = currentPage * chatsPerPage;
  const indexOfFirstChat = indexOfLastChat - chatsPerPage;
  const currentChats = filteredChats.slice(indexOfFirstChat, indexOfLastChat);
  
  // Get unique chat types for filter dropdown
  const chatTypes = ['all', ...Array.from(new Set(chats.map(chat => chat.type)))];

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
                      {type === 'all' ? 'All Types' : type.charAt(0).toUpperCase() + type.slice(1)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
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
              {searchQuery || selectedType !== 'all' 
                ? 'Try adjusting your search filters' 
                : 'Start a new chat to get started'}
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
                  className="overflow-hidden hover:shadow-md transition-shadow"
                >
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="line-clamp-1">{chat.title || `Chat ${chat.id}`}</CardTitle>
                        <CardDescription>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3.5 w-3.5" />
                            <span>{format(new Date(chat.created_at), 'MMM d, yyyy')}</span>
                          </span>
                        </CardDescription>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Open menu</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => window.location.href = `/dashboard/${chat.search_space_id}/researcher/${chat.id}`}>
                            <ExternalLink className="mr-2 h-4 w-4" />
                            <span>View Chat</span>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem 
                            className="text-destructive focus:text-destructive"
                            onClick={() => {
                              setChatToDelete({ id: chat.id, title: chat.title || `Chat ${chat.id}` });
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
                  <CardContent>
                    <div className="text-sm text-muted-foreground line-clamp-3">
                      {chat.messages && chat.messages.length > 0 
                        ? typeof chat.messages[0] === 'string'
                          ? chat.messages[0]
                          : chat.messages[0]?.content || 'No message content'
                        : 'No messages in this chat.'}
                    </div>
                  </CardContent>
                  <CardFooter className="flex justify-between pt-2">
                    <div className="flex items-center text-xs text-muted-foreground">
                      <MessageCircleMore className="mr-1 h-3.5 w-3.5" />
                      <span>{chat.messages?.length || 0} messages</span>
                    </div>
                    <Badge variant="secondary" className="text-xs">
                      <Tag className="mr-1 h-3 w-3" />
                      {chat.type || 'Unknown'}
                    </Badge>
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
                  className={currentPage <= 1 ? 'pointer-events-none opacity-50' : ''}
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
                  className={currentPage >= totalPages ? 'pointer-events-none opacity-50' : ''}
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
              Are you sure you want to delete <span className="font-medium">{chatToDelete?.title}</span>? This action cannot be undone.
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
    </motion.div>
  );
} 