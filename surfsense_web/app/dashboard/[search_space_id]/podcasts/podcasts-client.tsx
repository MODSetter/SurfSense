'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { format } from 'date-fns';
import { 
  Search, Calendar, Trash2, MoreHorizontal, Podcast, 
  Play, Pause, SkipForward, SkipBack, Volume2, VolumeX
} from 'lucide-react';

// UI Components
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';
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
import { toast } from "sonner";

interface Podcast {
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

const pageVariants = {
  initial: { opacity: 0 },
  enter: { opacity: 1, transition: { duration: 0.3, ease: 'easeInOut' } },
  exit: { opacity: 0, transition: { duration: 0.3, ease: 'easeInOut' } }
};

const podcastCardVariants = {
  initial: { y: 20, opacity: 0 },
  animate: { y: 0, opacity: 1 },
  exit: { y: -20, opacity: 0 }
};

const MotionCard = motion(Card);

export default function PodcastsPageClient({ searchSpaceId }: PodcastsPageClientProps) {
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);
  const [filteredPodcasts, setFilteredPodcasts] = useState<Podcast[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState<string>('newest');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [podcastToDelete, setPodcastToDelete] = useState<{ id: number, title: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Audio player state
  const [currentPodcast, setCurrentPodcast] = useState<Podcast | null>(null);
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
  const PODCAST_IMAGE_URL = "https://static.vecteezy.com/system/resources/thumbnails/002/157/611/small_2x/illustrations-concept-design-podcast-channel-free-vector.jpg";

  // Fetch podcasts from API
  useEffect(() => {
    const fetchPodcasts = async () => {
      try {
        setIsLoading(true);
        
        // Get token from localStorage
        const token = localStorage.getItem('surfsense_bearer_token');
        
        if (!token) {
          setError('Authentication token not found. Please log in again.');
          setIsLoading(false);
          return;
        }

        // Fetch all podcasts for this search space
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/`,
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
          throw new Error(`Failed to fetch podcasts: ${response.status} ${errorData?.detail || ''}`);
        }

        const data: Podcast[] = await response.json();
        setPodcasts(data);
        setFilteredPodcasts(data);
        setError(null);
      } catch (error) {
        console.error('Error fetching podcasts:', error);
        setError(error instanceof Error ? error.message : 'Unknown error occurred');
        setPodcasts([]);
        setFilteredPodcasts([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPodcasts();
  }, [searchSpaceId]);

  // Filter and sort podcasts based on search query and sort order
  useEffect(() => {
    let result = [...podcasts];
    
    // Filter by search term
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(podcast => 
        podcast.title.toLowerCase().includes(query)
      );
    }
    
    // Filter by search space
    result = result.filter(podcast => 
      podcast.search_space_id === parseInt(searchSpaceId)
    );
    
    // Sort podcasts
    result.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
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
      audioRef.current.volume = newVolume;
      setVolume(newVolume);
      
      if (newVolume === 0) {
        setIsMuted(true);
      } else if (isMuted) {
        setIsMuted(false);
      }
    }
  };

  // Toggle mute
  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  // Skip forward 10 seconds
  const skipForward = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.min(audioRef.current.duration, audioRef.current.currentTime + 10);
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
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  // Play podcast - Fetch blob and set object URL
  const playPodcast = async (podcast: Podcast) => {
    // If the same podcast is selected, just toggle play/pause
    if (currentPodcast && currentPodcast.id === podcast.id) {
      togglePlayPause();
      return;
    }

    // Revoke previous object URL if exists
    if (currentObjectUrlRef.current) {
      URL.revokeObjectURL(currentObjectUrlRef.current);
      currentObjectUrlRef.current = null;
    }
    
    // Reset player state and show loading
    setCurrentPodcast(podcast);
    setAudioSrc(undefined);
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);
    setIsAudioLoading(true);
    
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      if (!token) {
        toast.error('Authentication token not found.');
        setIsAudioLoading(false);
        return;
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcast.id}/stream`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch audio stream: ${response.statusText}`);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      currentObjectUrlRef.current = objectUrl;
      setAudioSrc(objectUrl);
      
      // Let the audio element load the new src
      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current.load();
          audioRef.current.play()
            .then(() => {
              setIsPlaying(true);
            })
            .catch(error => {
              console.error('Error playing audio:', error);
              toast.error('Failed to play audio.');
              setIsPlaying(false);
            });
        }
      }, 50);

    } catch (error) {
      console.error('Error fetching or playing podcast:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to load podcast audio.');
      setCurrentPodcast(null);
    } finally {
      setIsAudioLoading(false);
    }
  };

  // Function to handle podcast deletion
  const handleDeletePodcast = async () => {
    if (!podcastToDelete) return;
    
    setIsDeleting(true);
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      if (!token) {
        setIsDeleting(false);
        return;
      }
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/podcasts/${podcastToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete podcast: ${response.statusText}`);
      }
      
      // Close dialog and refresh podcasts
      setDeleteDialogOpen(false);
      setPodcastToDelete(null);
      
      // Update local state by removing the deleted podcast
      setPodcasts(prevPodcasts => prevPodcasts.filter(podcast => podcast.id !== podcastToDelete.id));
      
      // If the current playing podcast is deleted, stop playback
      if (currentPodcast && currentPodcast.id === podcastToDelete.id) {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        setCurrentPodcast(null);
        setIsPlaying(false);
      }
      
      toast.success('Podcast deleted successfully');
    } catch (error) {
      console.error('Error deleting podcast:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete podcast');
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
                ? 'Try adjusting your search filters' 
                : 'Generate podcasts from your chats to get started'}
            </p>
          </div>
        )}
        
        {/* Podcast Grid */}
        {!isLoading && !error && filteredPodcasts.length > 0 && (
          <AnimatePresence mode="wait">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredPodcasts.map((podcast, index) => (
                <MotionCard
                  key={podcast.id}
                  variants={podcastCardVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  transition={{ duration: 0.2, delay: index * 0.05 }}
                  className={`
                    bg-card/60 dark:bg-card/40 backdrop-blur-lg rounded-xl p-4 
                    shadow-lg hover:shadow-xl transition-all duration-300 
                    border-border overflow-hidden 
                    ${currentPodcast?.id === podcast.id ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : ''}
                  `}
                  layout
                >
                  <div 
                    className="relative w-full aspect-[16/10] mb-4 rounded-lg overflow-hidden group cursor-pointer"
                    onClick={() => playPodcast(podcast)}
                  >
                    {/* Podcast image */}
                    <img 
                      src={PODCAST_IMAGE_URL} 
                      alt="Podcast illustration" 
                      className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105 brightness-[0.85] contrast-[1.1]"
                      loading="lazy"
                    />
                    
                    {/* Overlay for better contrast with controls */}
                    <div className="absolute inset-0 bg-black/20 group-hover:bg-black/30 transition-colors"></div>
                    
                    {/* Loading indicator */}
                    {currentPodcast?.id === podcast.id && isAudioLoading && (
                      <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
                        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
                      </div>
                    )}

                    {/* Play button */}
                    {!(currentPodcast?.id === podcast.id && (isPlaying || isAudioLoading)) && (
                      <Button
                        variant="outline"
                        size="icon"
                        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-14 w-14 rounded-full 
                          bg-background/70 hover:bg-background/90 backdrop-blur-sm scale-90 group-hover:scale-100 
                          transition-transform duration-200 z-0 shadow-lg"
                        onClick={(e) => {
                          e.stopPropagation();
                          playPodcast(podcast);
                        }}
                        disabled={isAudioLoading}
                      >
                        <Play className="h-7 w-7 ml-1" /> 
                      </Button>
                    )}
                    
                    {/* Pause button */}
                    {currentPodcast?.id === podcast.id && isPlaying && !isAudioLoading && (
                      <Button
                        variant="outline"
                        size="icon"
                        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-14 w-14 rounded-full 
                          bg-background/70 hover:bg-background/90 backdrop-blur-sm scale-90 group-hover:scale-100 
                          transition-transform duration-200 z-0 shadow-lg"
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePlayPause();
                        }}
                        disabled={isAudioLoading}
                      >
                        <Pause className="h-7 w-7" /> 
                      </Button>
                    )}
                  </div>

                  <div className="mb-3 px-1">
                    <h3 className="text-base font-semibold text-foreground truncate" title={podcast.title}>
                      {podcast.title || 'Untitled Podcast'}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
                      <Calendar className="h-3 w-3" /> 
                      {format(new Date(podcast.created_at), 'MMM d, yyyy')}
                    </p>
                  </div>
                  
                  {currentPodcast?.id === podcast.id && !isAudioLoading && (
                    <div className="mb-3 px-1">
                      <div
                        className="h-1.5 bg-muted rounded-full cursor-pointer group relative"
                        onClick={(e) => {
                          if (!audioRef.current || !duration) return;
                          const container = e.currentTarget;
                          const rect = container.getBoundingClientRect();
                          const x = e.clientX - rect.left;
                          const percentage = Math.max(0, Math.min(1, x / rect.width));
                          const newTime = percentage * duration;
                          handleSeek([newTime]);
                        }}
                      >
                        <div
                          className="h-full bg-primary rounded-full relative transition-all duration-75 ease-linear"
                          style={{ width: `${(currentTime / duration) * 100}%` }}
                        >
                          <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 
                            bg-primary rounded-full shadow-md transform scale-0 translate-x-1/2 
                            group-hover:scale-100 transition-transform"
                          />
                        </div>
                      </div>
                      <div className="flex justify-between mt-1.5 text-xs text-muted-foreground">
                        <span>{formatTime(currentTime)}</span>
                        <span>{formatTime(duration)}</span>
                      </div>
                    </div>
                  )}

                  {currentPodcast?.id === podcast.id && !isAudioLoading && (
                    <div className="flex items-center justify-between px-2 mt-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={skipBackward}
                        className="w-9 h-9 text-muted-foreground hover:text-primary transition-colors"
                        title="Rewind 10 seconds"
                        disabled={!duration}
                      >
                        <SkipBack className="w-5 h-5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={togglePlayPause}
                        className="w-10 h-10 text-primary hover:bg-primary/10 rounded-full transition-colors"
                        disabled={!duration}
                      >
                        {isPlaying ?
                          <Pause className="w-6 h-6" /> :
                          <Play className="w-6 h-6 ml-0.5" />
                        }
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={skipForward}
                        className="w-9 h-9 text-muted-foreground hover:text-primary transition-colors"
                        title="Forward 10 seconds"
                        disabled={!duration}
                      >
                        <SkipForward className="w-5 h-5" />
                      </Button>
                    </div>
                  )}
                  
                  <div className="absolute top-2 right-2 z-20">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-7 w-7 bg-background/50 hover:bg-background/80 rounded-full backdrop-blur-sm">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Open menu</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => {
                              setPodcastToDelete({ id: podcast.id, title: podcast.title });
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
            </div>
          </AnimatePresence>
        )}
        
        {/* Current Podcast Player (Fixed at bottom) */}
        {currentPodcast && !isAudioLoading && audioSrc && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 100, opacity: 0 }}
            className="fixed bottom-0 left-0 right-0 bg-background border-t p-4 shadow-lg z-50"
          >
            <div className="container mx-auto">
              <div className="flex flex-col md:flex-row items-center gap-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-primary/20 rounded-md flex items-center justify-center">
                    <Podcast className="h-6 w-6 text-primary" />
                  </div>
                </div>
                
                <div className="flex-grow min-w-0">
                  <h4 className="font-medium text-sm line-clamp-1">{currentPodcast.title}</h4>
                  
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-grow">
                      <Slider
                        value={[currentTime]}
                        min={0}
                        max={duration || 100}
                        step={0.1}
                        onValueChange={handleSeek}
                      />
                    </div>
                    <div className="flex-shrink-0 text-xs text-muted-foreground whitespace-nowrap">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={skipBackward}
                    className="h-8 w-8"
                  >
                    <SkipBack className="h-4 w-4" />
                  </Button>
                  
                  <Button
                    variant="default"
                    size="icon"
                    onClick={togglePlayPause}
                    className="h-10 w-10 rounded-full"
                  >
                    {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
                  </Button>
                  
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={skipForward}
                    className="h-8 w-8"
                  >
                    <SkipForward className="h-4 w-4" />
                  </Button>
                  
                  <div className="hidden md:flex items-center gap-2 ml-4 w-28">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={toggleMute}
                      className="h-8 w-8"
                    >
                      {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    </Button>
                    
                    <Slider
                      value={[isMuted ? 0 : volume]}
                      min={0}
                      max={1}
                      step={0.01}
                      onValueChange={handleVolumeChange}
                      className="w-20"
                    />
                  </div>
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
              Are you sure you want to delete <span className="font-medium">{podcastToDelete?.title}</span>? This action cannot be undone.
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
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleMetadataLoaded}
        onEnded={() => setIsPlaying(false)}
        onError={(e) => {
          console.error('Audio error:', e);
          if (audioRef.current?.error?.code !== audioRef.current?.error?.MEDIA_ERR_ABORTED) {
             toast.error('Error playing audio.');
          }
        }}
      />
    </motion.div>
  );
} 