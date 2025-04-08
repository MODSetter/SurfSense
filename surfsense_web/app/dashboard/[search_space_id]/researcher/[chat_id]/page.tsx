"use client";
import React, { useRef, useEffect, useState } from 'react';
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
  SendHorizontal
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
  SegmentedControl,
  ConnectorButton as ConnectorButtonComponent,
  getConnectorIcon,
  getMainViewSources as getMainViewSourcesUtil,
  getFilteredSources as getFilteredSourcesUtil,
  getPaginatedDialogSources as getPaginatedDialogSourcesUtil,
  getSourcesCount as getSourcesCountUtil,
  useScrollToBottom,
  updateScrollIndicators as updateScrollIndicatorsUtil,
  useScrollIndicators,
  scrollTabsLeft as scrollTabsLeftUtil,
  scrollTabsRight as scrollTabsRightUtil,
  Source,
  ResearchMode,
  researcherOptions
} from '@/components/chat';
import { MarkdownViewer } from '@/components/markdown-viewer';
import { connectorSourcesMenu as defaultConnectorSourcesMenu } from '@/components/chat/connector-sources';
import { Logo } from '@/components/Logo';
import { useSearchSourceConnectors } from '@/hooks';

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
        {paginatedSources.map((source: any) => (
          <Card key={source.id} className="p-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
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
  const [showAnswer, setShowAnswer] = useState(true);
  const [activeTab, setActiveTab] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [sourcesPage, setSourcesPage] = useState(1);
  const [expandedSources, setExpandedSources] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [sourceFilter, setSourceFilter] = useState("");
  const tabsListRef = useRef<HTMLDivElement>(null);
  const [terminalExpanded, setTerminalExpanded] = useState(false);
  const [selectedConnectors, setSelectedConnectors] = useState<string[]>(["CRAWLED_URL"]);
  const [researchMode, setResearchMode] = useState<ResearchMode>("GENERAL");
  const [currentTime, setCurrentTime] = useState<string>('');
  const [currentDate, setCurrentDate] = useState<string>('');
  const [connectorSources, setConnectorSources] = useState<any[]>([]);
  const terminalMessagesRef = useRef<HTMLDivElement>(null);
  const { connectorSourceItems, isLoading: isLoadingConnectors } = useSearchSourceConnectors();

  const SOURCES_PER_PAGE = 5;
  const INITIAL_SOURCES_DISPLAY = 3;

  const { search_space_id, chat_id } = useParams();

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
        research_mode: researchMode
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

        console.log('Fetching chat details for chat ID:', chat_id);

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
        console.log('Chat details fetched:', chatData);

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


          console.log('Updating chat with title:', title);

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

          console.log('Chat updated successfully');
        }
      } catch (err) {
        console.error('Error updating chat:', err);
      }
    };

    updateChat();
  }, [messages, status, chat_id, researchMode, selectedConnectors, search_space_id]);

  // Log messages whenever they update and extract annotations from the latest assistant message if available
  useEffect(() => {
    console.log('Messages updated:', messages);

    // Extract annotations from the latest assistant message if available
    const assistantMessages = messages.filter(msg => msg.role === 'assistant');
    if (assistantMessages.length > 0) {
      const latestAssistantMessage = assistantMessages[assistantMessages.length - 1];
      if (latestAssistantMessage?.annotations) {
        const annotations = latestAssistantMessage.annotations as any[];

        // Debug log to track streaming annotations
        if (process.env.NODE_ENV === 'development') {
          console.log('Streaming annotations:', annotations);

          // Log counts of each annotation type
          const terminalInfoCount = annotations.filter(a => a.type === 'TERMINAL_INFO').length;
          const sourcesCount = annotations.filter(a => a.type === 'SOURCES').length;
          const answerCount = annotations.filter(a => a.type === 'ANSWER').length;

          console.log(`Annotation counts - Terminal: ${terminalInfoCount}, Sources: ${sourcesCount}, Answer: ${answerCount}`);
        }

        // Process SOURCES annotation - get the last one to ensure we have the latest
        const sourcesAnnotations = annotations.filter(
          (annotation) => annotation.type === 'SOURCES'
        );

        if (sourcesAnnotations.length > 0) {
          // Get the last SOURCES annotation to ensure we have the most recent one
          const latestSourcesAnnotation = sourcesAnnotations[sourcesAnnotations.length - 1];
          if (latestSourcesAnnotation.content) {
            setConnectorSources(latestSourcesAnnotation.content);
          }
        }

        // Check for terminal info annotations and scroll terminal to bottom if they exist
        const terminalInfoAnnotations = annotations.filter(
          (annotation) => annotation.type === 'TERMINAL_INFO'
        );

        if (terminalInfoAnnotations.length > 0) {
          // Schedule scrolling after the DOM has been updated
          setTimeout(scrollTerminalToBottom, 100);
        }
      }
    }
  }, [messages]);

  // Custom handleSubmit function to include selected connectors and answer type
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim() || status !== 'ready') return;

    // You can add additional logic here if needed
    // For example, validation for selected connectors
    if (selectedConnectors.length === 0) {
      alert("Please select at least one connector");
      return;
    }

    // Call the original handleSubmit from useChat
    handleChatSubmit(e);
  };

  // Reference to the messages container for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Function to scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Function to scroll terminal to bottom
  const scrollTerminalToBottom = () => {
    if (terminalMessagesRef.current) {
      terminalMessagesRef.current.scrollTop = terminalMessagesRef.current.scrollHeight;
    }
  };

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Set activeTab when connectorSources change
  useEffect(() => {
    if (connectorSources.length > 0) {
      setActiveTab(connectorSources[0].type);
    }
  }, [connectorSources]);

  // Scroll terminal to bottom when expanded
  useEffect(() => {
    if (terminalExpanded) {
      setTimeout(scrollTerminalToBottom, 300); // Wait for transition to complete
    }
  }, [terminalExpanded]);

  // Get total sources count for a connector type
  const getSourcesCount = (connectorType: string) => {
    return getSourcesCountUtil(connectorSources, connectorType);
  };

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

  // Function to get sources for the main view
  const getMainViewSources = (connector: any) => {
    return getMainViewSourcesUtil(connector, INITIAL_SOURCES_DISPLAY);
  };

  // Function to get filtered sources for the dialog with null check
  const getFilteredSourcesWithCheck = (connector: any, sourceFilter: string) => {
    if (!connector?.sources) return [];
    return getFilteredSourcesUtil(connector, sourceFilter);
  };

  // Function to get paginated dialog sources with null check
  const getPaginatedDialogSourcesWithCheck = (connector: any, sourceFilter: string, expandedSources: boolean, sourcesPage: number, sourcesPerPage: number) => {
    if (!connector?.sources) return [];
    return getPaginatedDialogSourcesUtil(connector, sourceFilter, expandedSources, sourcesPage, sourcesPerPage);
  };

  // Function to get a citation source by ID
  const getCitationSource = (citationId: number): Source | null => {
    if (!messages || messages.length === 0) return null;

    // Find the latest assistant message
    const assistantMessages = messages.filter(msg => msg.role === 'assistant');
    if (assistantMessages.length === 0) return null;

    const latestAssistantMessage = assistantMessages[assistantMessages.length - 1];
    if (!latestAssistantMessage?.annotations) return null;

    // Find all SOURCES annotations
    const annotations = latestAssistantMessage.annotations as any[];
    const sourcesAnnotations = annotations.filter(
      (annotation) => annotation.type === 'SOURCES'
    );

    // Get the latest SOURCES annotation
    if (sourcesAnnotations.length === 0) return null;
    const latestSourcesAnnotation = sourcesAnnotations[sourcesAnnotations.length - 1];

    if (!latestSourcesAnnotation.content) return null;

    // Flatten all sources from all connectors
    const allSources: Source[] = [];
    latestSourcesAnnotation.content.forEach((connector: ConnectorSource) => {
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
                      <MarkdownViewer content={message.content} getCitationSource={getCitationSource} className="text-sm" />
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
                        {message.annotations && (() => {
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
                        })()}
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

                      <Tabs
                        defaultValue={connectorSources.length > 0 ? connectorSources[0].type : "CRAWLED_URL"}
                        className="w-full"
                        onValueChange={setActiveTab}
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
                                  {connectorSources.map((connector) => (
                                    <TabsTrigger
                                      key={connector.id}
                                      value={connector.type}
                                      className="flex items-center gap-1 mx-1 data-[state=active]:bg-gray-100 dark:data-[state=active]:bg-gray-800 rounded-md"
                                    >
                                      {getConnectorIcon(connector.type)}
                                      <span className="hidden sm:inline ml-1">{connector.name.split(' ')[0]}</span>
                                      <span className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs">
                                        {getSourcesCount(connector.type)}
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

                        {connectorSources.map(connector => (
                          <TabsContent key={connector.id} value={connector.type} className="mt-0">
                            <div className="space-y-3">
                              {getMainViewSources(connector).map((source: any) => (
                                <Card key={source.id} className="p-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
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

                              {connector.sources.length > INITIAL_SOURCES_DISPLAY && (
                                <Dialog open={dialogOpen && activeTab === connector.type} onOpenChange={(open) => setDialogOpen(open)}>
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
                                      isLoadingMore={isLoadingMore}
                                    />
                                  </DialogContent>
                                </Dialog>
                              )}
                            </div>
                          </TabsContent>
                        ))}
                      </Tabs>
                    </div>

                    {/* Answer Section */}
                    <div className="mb-6">
                      {showAnswer && (
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
                                  getCitationSource={getCitationSource}
                                />
                              );
                            }

                            // Fallback to the message content if no ANSWER annotation is available
                            return <MarkdownViewer content={message.content} getCitationSource={getCitationSource} />;
                          })()}
                        </div>
                      )}
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
              placeholder={"Search about..."}
              value={input}
              onChange={handleInputChange}
              className="no-shadow-input border-0 focus-visible:ring-offset-0 focus-visible:ring-0 resize-none overflow-auto w-full flex-1 bg-transparent p-3 pb-1.5 text-sm outline-none placeholder:text-muted-foreground"
              disabled={status !== 'ready'}
            />
            {/* Send button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-full hover:bg-primary/10 hover:text-primary transition-colors"
              type="submit"
              disabled={status !== 'ready' || !input.trim()}
              aria-label="Send message"
            >
              <SendHorizontal className="h-4 w-4 text-primary" />
              <span className="sr-only">Send</span>
            </Button>
          </form>
          <div className="flex items-center justify-between px-2 py-1 mt-8">
            <div className="flex items-center gap-4">
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

              {/* Research Mode Segmented Control */}
              <SegmentedControl<ResearchMode>
                value={researchMode}
                onChange={setResearchMode}
                options={researcherOptions}
              />
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