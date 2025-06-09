"use client";
import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { useChat } from '@ai-sdk/react';
import { useParams } from 'next/navigation';
import {
  Loader2,
  X,
  Search,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Check,
  ArrowDown,
  CircleUser,
  Database,
  SendHorizontal,
  FileText,
  Grid3x3,
  FolderOpen,
  Upload,
  ChevronDown,
  Filter,
  Brain,
  Zap
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ConnectorButton as ConnectorButtonComponent,
  getConnectorIcon,
  getFilteredSources as getFilteredSourcesUtil,
  getPaginatedDialogSources as getPaginatedDialogSourcesUtil,
  useScrollToBottom,
  updateScrollIndicators as updateScrollIndicatorsUtil,
  useScrollIndicators,
  scrollTabsLeft as scrollTabsLeftUtil,
  scrollTabsRight as scrollTabsRightUtil,
  Source,
  ResearchMode,
  ResearchModeControl
} from '@/components/chat';
import { MarkdownViewer } from '@/components/markdown-viewer';
import { Logo } from '@/components/Logo';
import { useSearchSourceConnectors } from '@/hooks';
import { useDocuments } from '@/hooks/use-documents';
import { useLLMConfigs, useLLMPreferences } from '@/hooks/use-llm-configs';

interface SourceItem {
  id: number;
  title: string;
  description: string;
  url: string;
  connectorType?: string;
}

interface ConnectorSource {
  id: number;
  name: string;
  type: string;
  sources: SourceItem[];
}

type DocumentType = "EXTENSION" | "CRAWLED_URL" | "SLACK_CONNECTOR" | "NOTION_CONNECTOR" | "FILE" | "YOUTUBE_VIDEO" | "GITHUB_CONNECTOR" | "LINEAR_CONNECTOR" | "DISCORD_CONNECTOR";


/**
 * Skeleton loader for document items
 */
const DocumentSkeleton = () => (
  <div className="flex items-start gap-3 p-3 rounded-md border">
    <Skeleton className="flex-shrink-0 w-6 h-6 mt-0.5" />
    <div className="flex-1 space-y-2">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="h-3 w-full" />
    </div>
    <Skeleton className="flex-shrink-0 w-4 h-4" />
  </div>
);

/**
 * Enhanced document type filter dropdown
 */
const DocumentTypeFilter = ({ 
  value, 
  onChange, 
  counts 
}: { 
  value: DocumentType | "ALL"; 
  onChange: (value: DocumentType | "ALL") => void;
  counts: Record<string, number>;
}) => {
  const getTypeLabel = (type: DocumentType | "ALL") => {
    if (type === "ALL") return "All Types";
    return type.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
  };

  const getTypeIcon = (type: DocumentType | "ALL") => {
    if (type === "ALL") return <Filter className="h-4 w-4" />;
    return getConnectorIcon(type);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1">
          {getTypeIcon(value)}
          <span className="hidden sm:inline">{getTypeLabel(value)}</span>
          <ChevronDown className="h-3 w-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Document Types</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {Object.entries(counts).map(([type, count]) => (
          <DropdownMenuItem
            key={type}
            onClick={() => onChange(type as DocumentType | "ALL")}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              {getTypeIcon(type as DocumentType | "ALL")}
              <span>{getTypeLabel(type as DocumentType | "ALL")}</span>
            </div>
            <Badge variant="secondary" className="text-xs">
              {count}
            </Badge>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

/**
 * Button that displays selected connectors and opens connector selection dialog
 */
const ConnectorButton = ({ selectedConnectors, onClick }: { selectedConnectors: string[], onClick: () => void }) => {
  const { connectorSourceItems } = useSearchSourceConnectors();
  
  return (
    <ConnectorButtonComponent
      selectedConnectors={selectedConnectors}
      onClick={onClick}
      connectorSources={connectorSourceItems}
    />
  );
};

/**
 * Button that displays selected documents count and opens document selection dialog
 */
const DocumentSelectorButton = ({ 
  selectedDocuments, 
  onClick, 
  documentsCount 
}: { 
  selectedDocuments: number[], 
  onClick: () => void,
  documentsCount: number 
}) => {
  return (
    <div className="relative">
      <Button
        variant="outline"
        onClick={onClick}
        className="h-8 px-2 text-xs font-medium transition-colors border-border bg-background hover:bg-muted/50"
      >
        <FolderOpen className="h-3 w-3" />
      </Button>
      {selectedDocuments.length > 0 && (
        <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-primary text-primary-foreground text-xs font-medium flex items-center justify-center leading-none">
          {selectedDocuments.length > 99 ? '99+' : selectedDocuments.length}
        </span>
      )}
      {selectedDocuments.length === 0 && (
        <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-muted text-muted-foreground text-xs font-medium flex items-center justify-center leading-none">
          0
        </span>
      )}
    </div>
  );
};

// Create a wrapper component for the sources dialog content
const SourcesDialogContent = ({ 
  connector, 
  sourceFilter, 
  expandedSources, 
  sourcesPage, 
  setSourcesPage,
  setSourceFilter,
  setExpandedSources,
  isLoadingMore 
}: { 
  connector: any; 
  sourceFilter: string; 
  expandedSources: boolean; 
  sourcesPage: number; 
  setSourcesPage: React.Dispatch<React.SetStateAction<number>>;
  setSourceFilter: React.Dispatch<React.SetStateAction<string>>;
  setExpandedSources: React.Dispatch<React.SetStateAction<boolean>>;
  isLoadingMore: boolean;
}) => {
  // Safely access sources with fallbacks
  const sources = connector?.sources || [];
  
  // Safe versions of utility functions
  const getFilteredSourcesSafe = () => {
    if (!sources.length) return [];
    return getFilteredSourcesUtil(connector, sourceFilter);
  };
  
  const getPaginatedSourcesSafe = () => {
    if (!sources.length) return [];
    return getPaginatedDialogSourcesUtil(
      connector,
      sourceFilter,
      expandedSources,
      sourcesPage,
      5 // SOURCES_PER_PAGE
    );
  };
  
  const filteredSources = getFilteredSourcesSafe() || [];
  const paginatedSources = getPaginatedSourcesSafe() || [];
  
  // Description text
  const descriptionText = sourceFilter
    ? `Found ${filteredSources.length} sources matching "${sourceFilter}"`
    : `Viewing ${paginatedSources.length} of ${sources.length} sources`;
    
  if (paginatedSources.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No sources found matching "{sourceFilter}"</p>
        <Button
          variant="ghost"
          className="mt-2 text-sm"
          onClick={() => setSourceFilter("")}
        >
          Clear search
        </Button>
      </div>
    );
  }
  
  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          {getConnectorIcon(connector.type)}
          <span>{connector.name} Sources</span>
        </DialogTitle>
        <DialogDescription className="dark:text-gray-400">
          {descriptionText}
        </DialogDescription>
      </DialogHeader>

      <div className="relative my-4">
        <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
        <Input
          placeholder="Search sources..."
          className="pl-8 pr-4"
          value={sourceFilter}
          onChange={(e) => {
            setSourceFilter(e.target.value);
            setSourcesPage(1);
            setExpandedSources(false);
          }}
        />
        {sourceFilter && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-1/2 transform -translate-y-1/2 h-4 w-4"
            onClick={() => {
              setSourceFilter("");
              setSourcesPage(1);
              setExpandedSources(false);
            }}
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>

      <div className="space-y-3 mt-4">
        {paginatedSources.map((source: any, index: number) => (
          <Card key={`${connector.type}-${source.id}-${index}`} className="p-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center">
                {getConnectorIcon(connector.type)}
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-sm">{source.title}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{source.description}</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => window.open(source.url, '_blank')}
              >
                <ExternalLink className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        ))}

        {!expandedSources && paginatedSources.length < filteredSources.length && (
          <Button
            variant="ghost"
            className="w-full text-sm text-gray-500 dark:text-gray-400"
            onClick={() => {
              setSourcesPage(prev => prev + 1);
            }}
            disabled={isLoadingMore}
          >
            {isLoadingMore ? (
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : (
              `Load ${Math.min(5, filteredSources.length - paginatedSources.length)} More Sources`
            )}
          </Button>
        )}

        {expandedSources && filteredSources.length > 10 && (
          <div className="text-center text-sm text-gray-500 dark:text-gray-400 pt-2">
            Showing all {filteredSources.length} sources
          </div>
        )}
      </div>
    </>
  );
};

const ChatPage = () => {
  const [token, setToken] = React.useState<string | null>(null);
  const [dialogOpenId, setDialogOpenId] = useState<number | null>(null);
  const [sourcesPage, setSourcesPage] = useState(1);
  const [expandedSources, setExpandedSources] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("");
  const tabsListRef = useRef<HTMLDivElement>(null);
  const [terminalExpanded, setTerminalExpanded] = useState(false);
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>([]);
  const [searchMode, setSearchMode] = useState<'DOCUMENTS' | 'CHUNKS'>('DOCUMENTS');
  const [researchMode, setResearchMode] = useState<ResearchMode>("QNA");
  const [currentTime, setCurrentTime] = useState<string>('');
  const [currentDate, setCurrentDate] = useState<string>('');
  const terminalMessagesRef = useRef<HTMLDivElement>(null);
  const { connectorSourceItems, isLoading: isLoadingConnectors } = useSearchSourceConnectors();
  const { llmConfigs } = useLLMConfigs();
  const { preferences, updatePreferences } = useLLMPreferences();

  const INITIAL_SOURCES_DISPLAY = 3;

  const { search_space_id, chat_id } = useParams();
  
  // Document selection state
  const [selectedDocuments, setSelectedDocuments] = useState<number[]>([]);
  const [documentFilter, setDocumentFilter] = useState("");
  const [debouncedDocumentFilter, setDebouncedDocumentFilter] = useState("");
  const [documentTypeFilter, setDocumentTypeFilter] = useState<DocumentType | "ALL">("ALL");
  const [documentsPage, setDocumentsPage] = useState(1);
  const [documentsPerPage] = useState(10);
  const { documents, loading: isLoadingDocuments, error: documentsError } = useDocuments(Number(search_space_id));

  // Debounced search effect (proper implementation)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedDocumentFilter(documentFilter);
      setDocumentsPage(1); // Reset page when search changes
    }, 300);

    return () => {
      clearTimeout(handler);
    };
  }, [documentFilter]);

  // Memoized filtered and paginated documents
  const filteredDocuments = useMemo(() => {
    if (!documents) return [];
    
    return documents.filter(doc => {
      const matchesSearch = doc.title.toLowerCase().includes(debouncedDocumentFilter.toLowerCase()) ||
                           doc.content.toLowerCase().includes(debouncedDocumentFilter.toLowerCase());
      const matchesType = documentTypeFilter === "ALL" || doc.document_type === documentTypeFilter;
      return matchesSearch && matchesType;
    });
  }, [documents, debouncedDocumentFilter, documentTypeFilter]);

  const paginatedDocuments = useMemo(() => {
    const startIndex = (documentsPage - 1) * documentsPerPage;
    return filteredDocuments.slice(startIndex, startIndex + documentsPerPage);
  }, [filteredDocuments, documentsPage, documentsPerPage]);

  const totalPages = Math.ceil(filteredDocuments.length / documentsPerPage);

  // Document type counts for filter dropdown
  const documentTypeCounts = useMemo(() => {
    if (!documents) return {};
    
    const counts: Record<string, number> = { ALL: documents.length };
    documents.forEach(doc => {
      counts[doc.document_type] = (counts[doc.document_type] || 0) + 1;
    });
    return counts;
  }, [documents]);

  // Callback to handle document selection
  const handleDocumentToggle = useCallback((documentId: number) => {
    setSelectedDocuments(prev => 
      prev.includes(documentId)
        ? prev.filter(id => id !== documentId)
        : [...prev, documentId]
    );
  }, []);

  // Function to scroll terminal to bottom
  const scrollTerminalToBottom = () => {
    if (terminalMessagesRef.current) {
      terminalMessagesRef.current.scrollTop = terminalMessagesRef.current.scrollHeight;
    }
  };

  // Get token from localStorage on client side only
  React.useEffect(() => {
    setToken(localStorage.getItem('surfsense_bearer_token'));
  }, []);

  // Set the current time only on the client side after initial render
  useEffect(() => {
    setCurrentDate(new Date().toISOString().split('T')[0]);
    setCurrentTime(new Date().toTimeString().split(' ')[0]);
  }, []);



  // Add this CSS to remove input shadow and improve the UI
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const style = document.createElement('style');
      style.innerHTML = `
        .no-shadow-input {
          box-shadow: none !important;
        }
        .no-shadow-input:focus-visible {
          box-shadow: none !important;
          outline: none !important;
        }
        .shadcn-selector {
          transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
          border: 1px solid hsl(var(--border));
          background-color: transparent;
          position: relative;
          overflow: hidden;
        }
        .shadcn-selector:hover {
          background-color: hsl(var(--muted));
          border-color: hsl(var(--primary) / 0.5);
        }
        .shadcn-selector:after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 0;
          background: hsl(var(--primary) / 0.1);
          transition: height 300ms ease;
        }
        .shadcn-selector:hover:after {
          height: 100%;
        }
        .shadcn-selector-primary {
          color: hsl(var(--primary));
          border-color: hsl(var(--primary) / 0.3);
        }
        .shadcn-selector-primary:hover {
          border-color: hsl(var(--primary));
          background-color: hsl(var(--primary) / 0.1);
        }
        /* Fix for scrollbar layout shifts */
        html {
          overflow-y: scroll;
        }
        body {
          scrollbar-gutter: stable;
        }
        /* For Firefox */
        * {
          scrollbar-width: thin;
        }
        /* For Webkit browsers */
        ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        ::-webkit-scrollbar-thumb {
          background-color: rgba(155, 155, 155, 0.5);
          border-radius: 20px;
        }
        /* Line clamp utility */
        .line-clamp-2 {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
      `;
      document.head.appendChild(style);

      return () => {
        document.head.removeChild(style);
      };
    }
  }, []);

  const { messages, input, handleInputChange, handleSubmit: handleChatSubmit, status, setMessages } = useChat({
    api: `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chat`,
    streamProtocol: 'data',
    headers: {
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: {
      data: {
        search_space_id: search_space_id,
        selected_connectors: selectedConnectors,
        research_mode: researchMode,
        search_mode: searchMode,
        document_ids_to_add_in_context: selectedDocuments
      }
    },
    onError: (error) => {
      console.error("Chat error:", error);
      // You can add additional error handling here if needed
    }
  });

  // Fetch chat details when component mounts
  useEffect(() => {
    const fetchChatDetails = async () => {
      try {
        if (!token) return; // Wait for token to be set

        // console.log('Fetching chat details for chat ID:', chat_id);

        const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chat_id)}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch chat details: ${response.statusText}`);
        }

        const chatData = await response.json();
        // console.log('Chat details fetched:', chatData);

        // Set research mode from chat data
        if (chatData.type) {
          setResearchMode(chatData.type as ResearchMode);
        }

        // Set connectors from chat data
        if (chatData.initial_connectors && Array.isArray(chatData.initial_connectors)) {
          setSelectedConnectors(chatData.initial_connectors);
        }

        // Set messages from chat data
        if (chatData.messages && Array.isArray(chatData.messages)) {
          setMessages(chatData.messages);
        }
      } catch (err) {
        console.error('Error fetching chat details:', err);
      }
    };

    if (token) {
      fetchChatDetails();
    }
  }, [token, chat_id, setMessages]);

  // Update chat when a conversation exchange is complete
  useEffect(() => {
    const updateChat = async () => {
      try {
        // Only update when:
        // 1. Status is ready (not loading)
        // 2. We have messages
        // 3. Last message is from assistant (completed response)
        if (
          status === 'ready' &&
          messages.length > 0 &&
          messages[messages.length - 1]?.role === 'assistant'
        ) {
          const token = localStorage.getItem('surfsense_bearer_token');
          if (!token) return;

          // Find the first user message to use as title
          const userMessages = messages.filter(msg => msg.role === 'user');
          if (userMessages.length === 0) return;

          // Use the first user message as the title
          const title = userMessages[0].content;


          // console.log('Updating chat with title:', title);

          // Update the chat
          const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chat_id)}`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
              type: researchMode,
              title: title,
              initial_connectors: selectedConnectors,
              messages: messages,
              search_space_id: Number(search_space_id)
            })
          });

          if (!response.ok) {
            throw new Error(`Failed to update chat: ${response.statusText}`);
          }

          // console.log('Chat updated successfully');
        }
      } catch (err) {
        console.error('Error updating chat:', err);
      }
    };

    updateChat();
  }, [messages, status, chat_id, researchMode, selectedConnectors, search_space_id]);

  // Check and scroll terminal when terminal info is available
  useEffect(() => {
    // Modified to trigger during streaming as well (removed status check)
    if (messages.length === 0) return;
    
    // Find the latest assistant message
    const assistantMessages = messages.filter(msg => msg.role === 'assistant');
    if (assistantMessages.length === 0) return;
    
    const latestAssistantMessage = assistantMessages[assistantMessages.length - 1];
    if (!latestAssistantMessage?.annotations) return;
    
    // Check for terminal info annotations
    const annotations = latestAssistantMessage.annotations as any[];
    const terminalInfoAnnotations = annotations.filter(a => a.type === 'TERMINAL_INFO');
    
    if (terminalInfoAnnotations.length > 0) {
      // Always scroll to bottom when terminal info is updated, even during streaming
      scrollTerminalToBottom();
    }
  }, [messages]); // Removed status from dependencies to ensure it triggers during streaming

  // Pure function to get connector sources for a specific message
  const getMessageConnectorSources = (message: any): any[] => {
    if (!message || message.role !== 'assistant' || !message.annotations) return [];

    // Find all SOURCES annotations
    const annotations = message.annotations as any[];
    const sourcesAnnotations = annotations.filter(a => a.type === 'SOURCES');

    // Get the latest SOURCES annotation
    if (sourcesAnnotations.length === 0) return [];
    const latestSourcesAnnotation = sourcesAnnotations[sourcesAnnotations.length - 1];
    
    if (!latestSourcesAnnotation.content) return [];
    
    return latestSourcesAnnotation.content;
  };

  // Custom handleSubmit function to include selected connectors and answer type
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim() || status !== 'ready') return;

    // Validation: require at least one connector OR at least one document
    // Note: Fast LLM selection updates user preferences automatically
    // if (selectedConnectors.length === 0 && selectedDocuments.length === 0) {
    //   alert("Please select at least one connector or document");
    //   return;
    // }

    // Call the original handleSubmit from useChat
    handleChatSubmit(e);
  };

  // Reference to the messages container for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Function to scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Reset sources page when new messages arrive
  useEffect(() => {
    // Reset pagination when we get new messages
    setSourcesPage(1);
    setExpandedSources(false);
  }, [messages]);

  // Scroll terminal to bottom when expanded
  useEffect(() => {
    if (terminalExpanded) {
      setTimeout(scrollTerminalToBottom, 300); // Wait for transition to complete
    }
  }, [terminalExpanded]);

  // Function to check scroll position and update indicators
  const updateScrollIndicators = () => {
    updateScrollIndicatorsUtil(tabsListRef as React.RefObject<HTMLDivElement>, setCanScrollLeft, setCanScrollRight);
  };

  // Initialize scroll indicators
  const updateIndicators = useScrollIndicators(
    tabsListRef as React.RefObject<HTMLDivElement>,
    setCanScrollLeft,
    setCanScrollRight
  );

  // Function to scroll tabs list left
  const scrollTabsLeft = () => {
    scrollTabsLeftUtil(tabsListRef as React.RefObject<HTMLDivElement>, updateIndicators);
  };

  // Function to scroll tabs list right
  const scrollTabsRight = () => {
    scrollTabsRightUtil(tabsListRef as React.RefObject<HTMLDivElement>, updateIndicators);
  };

  // Use the scroll to bottom hook
  useScrollToBottom(messagesEndRef as React.RefObject<HTMLDivElement>, [messages]);

  // Function to get a citation source by ID
  const getCitationSource = React.useCallback((citationId: number, messageIndex?: number): Source | null => {
    if (!messages || messages.length === 0) return null;

    // If no specific message index is provided, use the latest assistant message
    if (messageIndex === undefined) {
      // Find the latest assistant message
      const assistantMessages = messages.filter(msg => msg.role === 'assistant');
      if (assistantMessages.length === 0) return null;

      const latestAssistantMessage = assistantMessages[assistantMessages.length - 1];
      
      // Use our helper function to get sources
      const sources = getMessageConnectorSources(latestAssistantMessage);
      if (sources.length === 0) return null;

      // Flatten all sources from all connectors
      const allSources: Source[] = [];
      sources.forEach((connector: ConnectorSource) => {
        if (connector.sources && Array.isArray(connector.sources)) {
          connector.sources.forEach((source: SourceItem) => {
            allSources.push({
              id: source.id,
              title: source.title,
              description: source.description,
              url: source.url,
              connectorType: connector.type
            });
          });
        }
      });

      // Find the source with the matching ID
      const foundSource = allSources.find(source => source.id === citationId);

      return foundSource || null;
    } else {
      // Use the specific message by index
      const message = messages[messageIndex];
      
      // Use our helper function to get sources
      const sources = getMessageConnectorSources(message);
      if (sources.length === 0) return null;

      // Flatten all sources from all connectors
      const allSources: Source[] = [];
      sources.forEach((connector: ConnectorSource) => {
        if (connector.sources && Array.isArray(connector.sources)) {
          connector.sources.forEach((source: SourceItem) => {
            allSources.push({
              id: source.id,
              title: source.title,
              description: source.description,
              url: source.url,
              connectorType: connector.type
            });
          });
        }
      });

      // Find the source with the matching ID
      const foundSource = allSources.find(source => source.id === citationId);

      return foundSource || null;
    }
  }, [messages]);

  // Pure function for rendering terminal content - no hooks allowed here
  const renderTerminalContent = (message: any) => {
    if (!message.annotations) return null;

    // Get all TERMINAL_INFO annotations
    const terminalInfoAnnotations = (message.annotations as any[])
      .filter(a => a.type === 'TERMINAL_INFO');

    // Get the latest TERMINAL_INFO annotation
    const latestTerminalInfo = terminalInfoAnnotations.length > 0
      ? terminalInfoAnnotations[terminalInfoAnnotations.length - 1]
      : null;

    // Render the content of the latest TERMINAL_INFO annotation
    return latestTerminalInfo?.content.map((item: any, idx: number) => (
      <div key={idx} className="py-0.5 flex items-start text-gray-300">
        <span className="text-gray-500 text-xs mr-2 w-10 flex-shrink-0">[{String(idx).padStart(2, '0')}:{String(Math.floor(idx * 2)).padStart(2, '0')}]</span>
        <span className="mr-2 opacity-70">{'>'}</span>
        <span className={`
          ${item.type === 'info' ? 'text-blue-300' : ''}
          ${item.type === 'success' ? 'text-green-300' : ''}
          ${item.type === 'error' ? 'text-red-300' : ''}
          ${item.type === 'warning' ? 'text-yellow-300' : ''}
        `}>{item.text}</span>
      </div>
    ));
  };

  return (
    <>
      <div className="flex flex-col min-h-[calc(100vh-4rem)] min-w-4xl max-w-4xl mx-auto px-4 py-8 overflow-x-hidden justify-center gap-4">
        {messages.length === 0 && (
          <h2 className="flex gap-2 justify-center text-balance relative z-50 mx-auto mb-6 text-center text-2xl font-semibold tracking-tight text-gray-700 dark:text-neutral-300 md:text-7xl">
            <Logo className='w-16 h-16 rounded-md' />
            <div className='text-muted-foreground'>
              Surf{""}
              <div className="relative mx-auto inline-block w-max [filter:drop-shadow(0px_1px_3px_rgba(27,_37,_80,_0.14))]">
                <div className="text-black [text-shadow:0_0_rgba(0,0,0,0.1)] dark:text-white">
                  <span className="">Sense</span>
                </div>
              </div>
            </div>
          </h2>
        )}
        {messages?.map((message, index) => {
          if (message.role === 'user') {
            return (
              <div key={index} className="flex gap-2">
                <CircleUser className="w-10 h-10" strokeWidth={1} />
                <div className="flex-1">
                  <Card className="border-gray-300 dark:border-gray-700">
                    <CardContent className="p-3">
                      <MarkdownViewer 
                        content={message.content}
                        getCitationSource={(id) => getCitationSource(id, index)}
                        className="text-sm" 
                      />
                    </CardContent>
                  </Card>
                </div>
              </div>
            );
          }

          if (message.role === 'assistant') {
            return (
              <div key={index} className="flex-1">
                <Card className="border-gray-300 dark:border-gray-700">
                  <CardHeader className="p-3">
                    <CardTitle className="text-sm font-medium">Answer</CardTitle>
                  </CardHeader>
                  <CardContent className="p-3 pt-0">
                    {/* Status Messages Section */}
                    <Card className="mb-6 overflow-hidden border-gray-300 dark:border-gray-700">
                      <div className="p-3 border-b dark:border-gray-700 flex items-center justify-between bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center gap-2">
                          <div className="flex space-x-1.5">
                            <div className="w-3 h-3 rounded-full bg-red-500 cursor-pointer hover:opacity-80" onClick={() => setTerminalExpanded(false)}></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 cursor-pointer hover:opacity-80"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500 cursor-pointer hover:opacity-80" onClick={() => setTerminalExpanded(true)}></div>
                          </div>
                          <span className="font-medium ml-2 text-sm">surfsense-research-terminal</span>
                        </div>
                      </div>

                      <div
                        ref={terminalMessagesRef}
                        className={`p-4 overflow-y-auto font-mono text-sm bg-gray-900 dark:bg-gray-950 text-gray-200 leading-relaxed ${terminalExpanded ? 'h-[400px]' : 'max-h-[200px]'} transition-all duration-300 relative`}
                      >
                        <div className="text-gray-500 mb-2 text-xs border-b border-gray-800 pb-1">Last login: {currentDate} {currentTime}</div>
                        <div className="text-gray-500 mb-1 text-xs flex items-center">
                          <span className="text-green-400 mr-1">researcher@surfsense</span>
                          <span className="mr-1">:</span>
                          <span className="text-blue-400 mr-1">~/research</span>
                          <span className="mr-1">$</span>
                          <span>surfsense-researcher</span>
                        </div>
                        
                        {renderTerminalContent(message)}
                        
                        <div className="mt-2 flex items-center">
                          <span className="text-gray-500 text-xs mr-2 w-10 flex-shrink-0">[00:13]</span>
                          <span className="text-green-400 mr-1">researcher@surfsense</span>
                          <span className="mr-1">:</span>
                          <span className="text-blue-400 mr-1">~/research</span>
                          <span className="mr-1">$</span>
                          <div className="h-4 w-2 bg-gray-400 animate-pulse"></div>
                        </div>

                        {/* Terminal scroll button */}
                        <div className="absolute bottom-4 right-4">
                          <Button
                            onClick={scrollTerminalToBottom}
                            className="h-6 w-6 rounded-full bg-gray-800 hover:bg-gray-700"
                            variant="ghost"
                            size="icon"
                            title="Scroll to bottom"
                          >
                            <ArrowDown className="h-3 w-3 text-gray-400" />
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* Sources Section with Connector Tabs */}
                    <div className="mb-6">
                      <div className="flex items-center gap-2 mb-4">
                        <Database className="h-5 w-5 text-gray-500" />
                        <span className="font-medium">Sources</span>
                      </div>

                      {(() => {
                        // Get sources for this specific message
                        const messageConnectorSources = getMessageConnectorSources(message);
                        
                        if (messageConnectorSources.length === 0) {
                          return (
                            <div className="text-center py-8 text-gray-500 dark:text-gray-400 border border-dashed rounded-md">
                              <Database className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            </div>
                          );
                        }
                        
                        // Use these message-specific sources for the Tabs component
                        return (
                          <Tabs
                            defaultValue={messageConnectorSources.length > 0 ? messageConnectorSources[0].type : undefined}
                            className="w-full"
                          >
                            <div className="mb-4">
                              <div className="flex items-center">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={scrollTabsLeft}
                                  className="flex-shrink-0 mr-2 z-10"
                                  disabled={!canScrollLeft}
                                >
                                  <ChevronLeft className="h-4 w-4" />
                                </Button>

                                <div className="flex-1 overflow-hidden">
                                  <div className="flex overflow-x-auto hide-scrollbar" ref={tabsListRef} onScroll={updateScrollIndicators}>
                                    <TabsList className="flex-1 bg-transparent border-0 p-0 custom-tabs-list">
                                      {messageConnectorSources.map((connector) => (
                                        <TabsTrigger
                                          key={connector.id}
                                          value={connector.type}
                                          className="flex items-center gap-1 mx-1 data-[state=active]:bg-gray-100 dark:data-[state=active]:bg-gray-800 rounded-md"
                                        >
                                          {getConnectorIcon(connector.type)}
                                          <span className="hidden sm:inline ml-1">{connector.name.split(' ')[0]}</span>
                                          <span className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs">
                                            {connector.sources?.length || 0}
                                          </span>
                                        </TabsTrigger>
                                      ))}
                                    </TabsList>
                                  </div>
                                </div>

                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={scrollTabsRight}
                                  className="flex-shrink-0 ml-2 z-10"
                                  disabled={!canScrollRight}
                                >
                                  <ChevronRight className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>

                            {messageConnectorSources.map(connector => (
                              <TabsContent key={connector.id} value={connector.type} className="mt-0">
                                <div className="space-y-3">
                                  {connector.sources?.slice(0, INITIAL_SOURCES_DISPLAY)?.map((source: any, index: number) => (
                                    <Card key={`${connector.type}-${source.id}-${index}`} className="p-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
                                      <div className="flex items-start gap-3">
                                        <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center">
                                          {getConnectorIcon(connector.type)}
                                        </div>
                                        <div className="flex-1">
                                          <h3 className="font-medium text-sm">{source.title}</h3>
                                          <p className="text-sm text-gray-500 dark:text-gray-400">{source.description}</p>
                                        </div>
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-6 w-6"
                                          onClick={() => window.open(source.url, '_blank')}
                                        >
                                          <ExternalLink className="h-4 w-4" />
                                        </Button>
                                      </div>
                                    </Card>
                                  ))}

                                  {connector.sources?.length > INITIAL_SOURCES_DISPLAY && (
                                    <Dialog open={dialogOpenId === connector.id} onOpenChange={(open) => setDialogOpenId(open ? connector.id : null)}>
                                      <DialogTrigger asChild>
                                        <Button variant="ghost" className="w-full text-sm text-gray-500 dark:text-gray-400">
                                          Show {connector.sources.length - INITIAL_SOURCES_DISPLAY} More Sources
                                        </Button>
                                      </DialogTrigger>
                                      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto dark:border-gray-700">
                                        <SourcesDialogContent
                                          connector={connector}
                                          sourceFilter={sourceFilter}
                                          expandedSources={expandedSources}
                                          sourcesPage={sourcesPage}
                                          setSourcesPage={setSourcesPage}
                                          setSourceFilter={setSourceFilter}
                                          setExpandedSources={setExpandedSources}
                                          isLoadingMore={false}
                                        />
                                      </DialogContent>
                                    </Dialog>
                                  )}
                                </div>
                              </TabsContent>
                            ))}
                          </Tabs>
                        );
                      })()}
                    </div>

                    {/* Answer Section */}
                    <div className="mb-6">
                      {
                        <div className="prose dark:prose-invert max-w-none">
                          {message.annotations && (() => {
                            // Get all ANSWER annotations
                            const answerAnnotations = (message.annotations as any[])
                              .filter(a => a.type === 'ANSWER');

                            // Get the latest ANSWER annotation
                            const latestAnswer = answerAnnotations.length > 0
                              ? answerAnnotations[answerAnnotations.length - 1]
                              : null;

                            // If we have a latest ANSWER annotation with content, render it
                            if (latestAnswer?.content && latestAnswer.content.length > 0) {
                              return (
                                <MarkdownViewer
                                  content={latestAnswer.content.join('\n')}
                                  getCitationSource={(id) => getCitationSource(id, index)}
                                />
                              );
                            }

                            // Fallback to the message content if no ANSWER annotation is available
                            return <MarkdownViewer 
                              content={message.content} 
                              getCitationSource={(id) => getCitationSource(id, index)} 
                            />;
                          })()}
                        </div>
                      }
                    </div>
                    {/* Scroll to bottom button */}
                    <div className="fixed bottom-8 right-8">
                      <Button
                        onClick={scrollToBottom}
                        className="h-8 w-8 rounded-full bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600"
                        variant="ghost"
                        size="icon"
                      >
                        <ArrowDown className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            );
          }

          return null;
        })}

        {/* New Chat Input Form */}
        <div className="py-2 px-4 border border-border rounded-lg bg-background">
          <form onSubmit={handleSubmit} className="flex items-center gap-3">
            <Input
              type="text"
              placeholder={status === 'streaming' ? "Thinking..." : "Search about..."}
              value={input}
              onChange={handleInputChange}
              className={`no-shadow-input border-0 focus-visible:ring-offset-0 focus-visible:ring-0 resize-none overflow-auto w-full flex-1 bg-transparent p-3 pb-1.5 text-sm outline-none placeholder:text-muted-foreground transition-all duration-200 ${
                status === 'streaming' 
                  ? 'opacity-75 cursor-not-allowed animate-pulse' 
                  : ''
              }`}
              disabled={status !== 'ready'}
            />
            {/* Send button */}
            <Button
              variant="ghost"
              size="icon"
              className={`h-9 w-9 rounded-full hover:bg-primary/10 hover:text-primary transition-all duration-200 ${
                status === 'streaming' 
                  ? 'cursor-not-allowed opacity-75' 
                  : 'hover:scale-105'
              }`}
              type="submit"
              disabled={status !== 'ready' || !input.trim()}
              aria-label={status === 'streaming' ? 'Sending message' : 'Send message'}
            >
              {status === 'streaming' ? (
                <Loader2 className="h-4 w-4 text-primary animate-spin" />
              ) : (
                <SendHorizontal className="h-4 w-4 text-primary" />
              )}
              <span className="sr-only">
                {status === 'streaming' ? 'Sending...' : 'Send'}
              </span>
            </Button>
          </form>
          <div className="flex items-center justify-between px-2 py-2 mt-3">
            <div className="flex items-center gap-2 flex-wrap">
            {/* Enhanced Document Selection Dialog */}
            <Dialog>
              <DialogTrigger asChild>
                <DocumentSelectorButton
                  selectedDocuments={selectedDocuments}
                  onClick={() => { }}
                  documentsCount={documents?.length || 0}
                />
              </DialogTrigger>
              <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col">
                <DialogHeader className="flex-shrink-0">
                  <DialogTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FolderOpen className="h-5 w-5" />
                      <span>Select Documents</span>
                      <Badge variant="secondary" className="text-xs">
                        {selectedDocuments.length} selected
                      </Badge>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.open(`/dashboard/${search_space_id}/documents/upload`, '_blank')}
                      className="h-8"
                    >
                      <Upload className="h-3 w-3 mr-1.5" />
                      Upload
                    </Button>
                  </DialogTitle>
                  <DialogDescription>
                    Choose documents to include in your research context. Use filters and search to find specific documents.
                  </DialogDescription>
                </DialogHeader>

                {/* Enhanced Search and Filter Controls */}
                <div className="flex-shrink-0 space-y-3 py-4">
                  <div className="flex flex-col sm:flex-row gap-3">
                    {/* Search Input */}
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search documents by title or content..."
                        className="pl-10 pr-4"
                        value={documentFilter}
                        onChange={(e) => setDocumentFilter(e.target.value)}
                      />
                      {documentFilter && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 transform -translate-y-1/2 h-6 w-6"
                          onClick={() => setDocumentFilter("")}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      )}
                    </div>

                                         {/* Document Type Filter */}
                     <DocumentTypeFilter
                       value={documentTypeFilter}
                       onChange={(newType) => {
                         setDocumentTypeFilter(newType);
                         setDocumentsPage(1); // Reset to page 1 when filter changes
                       }}
                       counts={documentTypeCounts}
                     />
                  </div>

                  {/* Results Summary */}
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>
                      {isLoadingDocuments ? (
                        "Loading documents..."
                      ) : (
                        `Showing ${paginatedDocuments.length} of ${filteredDocuments.length} documents`
                      )}
                    </span>
                    {filteredDocuments.length > 0 && (
                      <span>
                        Page {documentsPage} of {totalPages}
                      </span>
                    )}
                  </div>
                </div>

                                 {/* Document List with Proper Scrolling */}
                 <div className="flex-1 min-h-0">
                   <div className="h-full max-h-[400px] overflow-y-auto space-y-2 pr-2">
                     {isLoadingDocuments ? (
                       // Enhanced skeleton loading
                       Array.from({ length: 6 }, (_, i) => (
                         <DocumentSkeleton key={i} />
                       ))
                     ) : documentsError ? (
                       <div className="flex flex-col items-center justify-center py-12 text-center">
                         <div className="rounded-full bg-destructive/10 p-3 mb-4">
                           <X className="h-6 w-6 text-destructive" />
                         </div>
                         <h3 className="font-medium text-destructive mb-1">Error loading documents</h3>
                         <p className="text-sm text-muted-foreground">Please try refreshing the page</p>
                       </div>
                     ) : filteredDocuments.length === 0 ? (
                       <div className="flex flex-col items-center justify-center py-12 text-center">
                         <div className="rounded-full bg-muted p-3 mb-4">
                           <FolderOpen className="h-6 w-6 text-muted-foreground" />
                         </div>
                         <h3 className="font-medium mb-1">No documents found</h3>
                         <p className="text-sm text-muted-foreground mb-4">
                           {documentFilter || documentTypeFilter !== "ALL"
                             ? "Try adjusting your search or filters"
                             : "Upload documents to get started"}
                         </p>
                         {(!documentFilter && documentTypeFilter === "ALL") && (
                           <Button
                             variant="outline"
                             size="sm"
                             onClick={() => window.open(`/dashboard/${search_space_id}/documents/upload`, '_blank')}
                           >
                             <Upload className="h-4 w-4 mr-2" />
                             Upload Documents
                           </Button>
                         )}
                       </div>
                     ) : (
                       // Enhanced document list
                       paginatedDocuments.map((document) => {
                         const isSelected = selectedDocuments.includes(document.id);
                         const typeLabel = document.document_type.replace(/_/g, ' ').toLowerCase();

                         return (
                           <div
                             key={document.id}
                             className={`group flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-all duration-200 ${
                               isSelected
                                 ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                                 : 'border-border hover:border-primary/50 hover:bg-muted/50'
                             }`}
                             onClick={() => handleDocumentToggle(document.id)}
                           >
                             <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center mt-1">
                               <div className={`${isSelected ? 'text-primary' : 'text-muted-foreground'} transition-colors`}>
                                 {getConnectorIcon(document.document_type)}
                               </div>
                             </div>
                             <div className="flex-1 min-w-0">
                               <div className="flex items-start justify-between gap-2 mb-2">
                                 <h3 className={`font-medium text-sm leading-5 ${isSelected ? 'text-foreground' : 'text-foreground'}`}>
                                   {document.title}
                                 </h3>
                                 {isSelected && (
                                   <div className="flex-shrink-0">
                                     <div className="rounded-full bg-primary p-1">
                                       <Check className="h-3 w-3 text-primary-foreground" />
                                     </div>
                                   </div>
                                 )}
                               </div>
                               <div className="flex items-center gap-2 mb-2">
                                 <Badge variant="outline" className="text-xs">
                                   {typeLabel}
                                 </Badge>
                                 <span className="text-xs text-muted-foreground">
                                   {new Date(document.created_at).toLocaleDateString()}
                                 </span>
                               </div>
                               <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                                 {document.content.substring(0, 200)}...
                               </p>
                             </div>
                           </div>
                         );
                       })
                     )}
                   </div>
                 </div>

                {/* Enhanced Pagination Controls */}
                {totalPages > 1 && (
                  <div className="flex-shrink-0 flex items-center justify-between pt-4 border-t">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDocumentsPage(p => Math.max(1, p - 1))}
                        disabled={documentsPage === 1}
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </Button>
                      <div className="flex items-center gap-1">
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                          const page = documentsPage <= 3 ? i + 1 : documentsPage - 2 + i;
                          if (page > totalPages) return null;
                          return (
                            <Button
                              key={page}
                              variant={page === documentsPage ? "default" : "outline"}
                              size="sm"
                              className="w-8 h-8 p-0"
                              onClick={() => setDocumentsPage(page)}
                            >
                              {page}
                            </Button>
                          );
                        })}
                        {totalPages > 5 && documentsPage < totalPages - 2 && (
                          <>
                            <span className="px-2 text-muted-foreground">...</span>
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-8 h-8 p-0"
                              onClick={() => setDocumentsPage(totalPages)}
                            >
                              {totalPages}
                            </Button>
                          </>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDocumentsPage(p => Math.min(totalPages, p + 1))}
                        disabled={documentsPage === totalPages}
                      >
                        Next
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}

                {/* Enhanced Footer */}
                <DialogFooter className="flex-shrink-0 flex flex-col sm:flex-row gap-3 pt-4">
                  <div className="flex items-center text-sm text-muted-foreground">
                    <span>
                      {selectedDocuments.length} of {filteredDocuments.length} document{selectedDocuments.length !== 1 ? 's' : ''} selected
                    </span>
                  </div>
                  <div className="flex gap-2 ml-auto">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedDocuments([])}
                      disabled={selectedDocuments.length === 0}
                    >
                      Clear All
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const visibleIds = paginatedDocuments.map(doc => doc.id);
                        const allVisibleSelected = visibleIds.every(id => selectedDocuments.includes(id));
                        
                        if (allVisibleSelected) {
                          setSelectedDocuments(prev => prev.filter(id => !visibleIds.includes(id)));
                        } else {
                          setSelectedDocuments(prev => [...new Set([...prev, ...visibleIds])]);
                        }
                      }}
                      disabled={paginatedDocuments.length === 0}
                    >
                      {paginatedDocuments.every(doc => selectedDocuments.includes(doc.id)) ? 'Deselect' : 'Select'} Page
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => {
                        const allFilteredIds = filteredDocuments.map(doc => doc.id);
                        const allSelected = allFilteredIds.every(id => selectedDocuments.includes(id));
                        
                        if (allSelected) {
                          setSelectedDocuments(prev => prev.filter(id => !allFilteredIds.includes(id)));
                        } else {
                          setSelectedDocuments(prev => [...new Set([...prev, ...allFilteredIds])]);
                        }
                      }}
                      disabled={filteredDocuments.length === 0}
                    >
                      {filteredDocuments.every(doc => selectedDocuments.includes(doc.id)) ? 'Deselect' : 'Select'} All Filtered
                    </Button>
                  </div>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Connector Selection Dialog */}
            <Dialog>
              <DialogTrigger asChild>
                <ConnectorButton
                  selectedConnectors={selectedConnectors}
                  onClick={() => { }}
                />
              </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Select Connectors</DialogTitle>
                    <DialogDescription>
                      Choose which data sources to include in your research
                    </DialogDescription>
                  </DialogHeader>

                  {/* Connector selection grid */}
                  <div className="grid grid-cols-2 gap-4 py-4">
                    {isLoadingConnectors ? (
                      <div className="col-span-2 flex justify-center py-4">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      </div>
                    ) : (
                      connectorSourceItems.map((connector) => {
                        const isSelected = selectedConnectors.includes(connector.type);

                        return (
                          <div
                            key={connector.id}
                            className={`flex items-center gap-2 p-2 rounded-md border cursor-pointer transition-colors ${isSelected
                              ? 'border-primary bg-primary/10'
                              : 'border-border hover:border-primary/50 hover:bg-muted'
                              }`}
                            onClick={() => {
                              setSelectedConnectors(
                                isSelected
                                  ? selectedConnectors.filter((type) => type !== connector.type)
                                  : [...selectedConnectors, connector.type]
                              );
                            }}
                            role="checkbox"
                            aria-checked={isSelected}
                            tabIndex={0}
                          >
                            <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-muted">
                              {getConnectorIcon(connector.type)}
                            </div>
                            <span className="flex-1 text-sm font-medium">{connector.name}</span>
                            {isSelected && <Check className="h-4 w-4 text-primary" />}
                          </div>
                        );
                      })
                    )}
                  </div>

                  <DialogFooter className="flex justify-between items-center">
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => setSelectedConnectors([])}
                      >
                        Clear All
                      </Button>
                      <Button
                        onClick={() => setSelectedConnectors(connectorSourceItems.map(c => c.type))}
                      >
                        Select All
                      </Button>
                    </div>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              {/* Search Mode Control */}
              <div className="flex gap-1">
                <Button
                  variant={searchMode === 'DOCUMENTS' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSearchMode('DOCUMENTS')}
                  className="h-8 px-3 text-xs"
                  title="Search full documents"
                >
                  <FileText className="h-3 w-3 mr-1.5" />
                  <span className="hidden sm:inline">Full</span>
                </Button>
                <Button
                  variant={searchMode === 'CHUNKS' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSearchMode('CHUNKS')}
                  className="h-8 px-3 text-xs"
                  title="Search document chunks"
                >
                  <Grid3x3 className="h-3 w-3 mr-1.5" />
                  <span className="hidden sm:inline">Chunks</span>
                </Button>
              </div>

              {/* Research Mode Control */}
              <div className="h-8 min-w-0 overflow-hidden">
                <ResearchModeControl
                  value={researchMode}
                  onChange={setResearchMode}
                />
              </div>

              {/* Fast LLM Selector */}
              <div className="h-8 min-w-0">
                <Select
                  value={preferences.fast_llm_id?.toString() || ""}
                  onValueChange={(value) => {
                    const llmId = value ? parseInt(value) : undefined;
                    updatePreferences({ fast_llm_id: llmId });
                  }}
                >
                  <SelectTrigger className="h-8 w-auto min-w-[120px] px-3 text-xs border-border bg-background hover:bg-muted/50">
                    <div className="flex items-center gap-2">
                      <Zap className="h-3 w-3 text-primary" />
                      <SelectValue placeholder="Fast LLM">
                        {preferences.fast_llm_id && (() => {
                          const selectedConfig = llmConfigs.find(config => config.id === preferences.fast_llm_id);
                          return selectedConfig ? (
                            <div className="flex items-center gap-1">
                              <span className="font-medium">{selectedConfig.provider}</span>
                              <span className="text-muted-foreground">•</span>
                              <span className="hidden sm:inline text-muted-foreground">{selectedConfig.name}</span>
                            </div>
                          ) : "Select LLM";
                        })()}
                      </SelectValue>
                    </div>
                  </SelectTrigger>
                  <SelectContent align="end" className="w-[280px]">
                    <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground border-b">
                      Answer LLM Selection
                    </div>
                    {llmConfigs.length === 0 ? (
                      <div className="px-2 py-3 text-center text-sm text-muted-foreground">
                        <Brain className="h-4 w-4 mx-auto mb-1 opacity-50" />
                        <p>No LLM configurations found</p>
                        <p className="text-xs">Configure models in Settings</p>
                      </div>
                    ) : (
                      llmConfigs.map((config) => (
                        <SelectItem key={config.id} value={config.id.toString()}>
                          <div className="flex items-center justify-between w-full">
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                                <Brain className="h-4 w-4 text-primary" />
                              </div>
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-sm">{config.name}</span>
                                  <Badge variant="outline" className="text-xs">
                                    {config.provider}
                                  </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground font-mono">
                                  {config.model_name}
                                </p>
                              </div>
                            </div>
                            {preferences.fast_llm_id === config.id && (
                              <div className="flex h-4 w-4 items-center justify-center rounded-full bg-primary">
                                <div className="h-2 w-2 rounded-full bg-primary-foreground" />
                              </div>
                            )}
                          </div>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>

        {/* Reference for auto-scrolling */}
        <div ref={messagesEndRef} />
      </div>
    </>
  );
};

export default ChatPage;