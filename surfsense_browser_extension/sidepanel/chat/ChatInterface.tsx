import { useState, useEffect, useCallback } from "react";
import { usePageContext } from "../context/PageContextProvider";
import { TokenInfoCard } from "../dexscreener/TokenInfoCard";
import { QuickCapture } from "./QuickCapture";
import { ChatHeader, type SearchSpace } from "./ChatHeader";
import { ChatMessages, type Message, type MessageWidget } from "./ChatMessages";
import { ChatInput, type AttachedFile } from "./ChatInput";
import { ThinkingStepsDisplay, type ThinkingStep } from "./ThinkingStepsDisplay";
import {
    MOCK_MODE,
    MOCK_SEARCH_SPACES,
    MOCK_WATCHLIST_TOKENS,
    MOCK_WATCHLIST_ALERTS,
    MOCK_SAFETY_SCORE,
    MOCK_SAFETY_FACTORS,
    MOCK_SAFETY_SOURCES,
    MOCK_WHALE_TRANSACTIONS,
    MOCK_TRADING_SUGGESTION,
    MOCK_PORTFOLIO,
} from "../mock/mockData";
import { SafetyScoreDisplay } from "../crypto/SafetyScoreDisplay";
import { WatchlistPanel } from "../crypto/WatchlistPanel";
import { AlertConfigModal } from "../crypto/AlertConfigModal";
import { DetectedTokensList } from "../components/DetectedTokensList";
import { useContextAction, getMessageForAction } from "../hooks/useContextAction";
import { useKeyboardShortcuts, getMessageForKeyboardAction } from "../hooks/useKeyboardShortcuts";
import type { WatchlistItem } from "../widgets";
import type { TokenData } from "../context/PageContextProvider";

type ViewMode = "chat" | "watchlist" | "safety";

/**
 * Natural language command patterns for conversational UX
 */
const COMMAND_PATTERNS = {
    // Epic 1: Basic commands
    ADD_WATCHLIST: /add\s+(\w+)\s+to\s+(my\s+)?watchlist/i,
    REMOVE_WATCHLIST: /remove\s+(\w+)\s+from\s+(my\s+)?watchlist/i,
    SHOW_WATCHLIST: /(show|display|view)\s+(my\s+)?watchlist/i,
    SET_ALERT: /set\s+alert\s+(if|when)\s+(\w+)\s+(drops?|pumps?|reaches?|changes?)\s+(\d+)%?/i,
    ANALYZE_TOKEN: /(analyze|research|check)\s+(\w+)/i,
    SAFETY_CHECK: /(is\s+)?(\w+)\s+(safe|risky|rug)/i,

    // Epic 2: Smart Monitoring & Alerts
    SHOW_WHALE_ACTIVITY: /(show|display|view)\s+(whale|large)\s+(activity|transactions|trades)/i,

    // Epic 3: Trading Intelligence
    TRADING_SUGGESTION: /(suggest|recommend|entry|exit|trade)\s+(for\s+)?(\w+)/i,
    SHOW_PORTFOLIO: /(show|display|view)\s+(my\s+)?portfolio/i,

    // Epic 4: Content Creation & Productivity
    CAPTURE_CHART: /(capture|screenshot|snap|grab)\s+(chart|graph)/i,
    GENERATE_THREAD: /(generate|create|write)\s+(thread|tweet)/i,
};

/**
 * Main chat interface for side panel
 * Adapts UI based on page context (e.g., shows token card on DexScreener)
 *
 * Features:
 * - Context-aware UI (DexScreener token detection)
 * - Welcome screen for new users
 * - Thinking steps visualization
 * - File attachments support
 * - Search space selection
 * - Watchlist panel
 * - Safety analysis view
 */
export function ChatInterface() {
    const { context, isMockMode } = usePageContext();
    const [messages, setMessages] = useState<Message[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
    const [selectedSpace, setSelectedSpace] = useState<SearchSpace>(
        MOCK_SEARCH_SPACES[0]
    );
    const [viewMode, setViewMode] = useState<ViewMode>("chat");
    const [showAlertModal, setShowAlertModal] = useState(false);
    const [selectedTokenForAlert, setSelectedTokenForAlert] = useState<string | null>(null);
    const [watchlistTokens, setWatchlistTokens] = useState(MOCK_WATCHLIST_TOKENS);
    const [isInWatchlist, setIsInWatchlist] = useState(false);

    // Context menu action hook
    const { pendingAction, clearAction } = useContextAction();

    // Keyboard shortcuts hook
    const { pendingAction: pendingKeyboardAction, clearAction: clearKeyboardAction } = useKeyboardShortcuts();

    // Mock user data - in production, this would come from auth context
    const userName = "Crypto Trader";

    // Handle context menu actions
    useEffect(() => {
        if (pendingAction) {
            const message = getMessageForAction(pendingAction);
            if (message) {
                // Auto-send the message
                handleSendMessage(message);
            }
            clearAction();
        }
    }, [pendingAction, clearAction]);

    // Handle keyboard shortcut actions
    useEffect(() => {
        if (pendingKeyboardAction) {
            const message = getMessageForKeyboardAction(pendingKeyboardAction);
            if (message) {
                // Auto-send the message
                handleSendMessage(message);
            }
            clearKeyboardAction();
        }
    }, [pendingKeyboardAction, clearKeyboardAction]);

    const handleSendMessage = async (content: string, attachments?: AttachedFile[]) => {
        console.log("Sending message:", content, attachments);
        setIsStreaming(true);
        setViewMode("chat");

        // Add user message
        const userMessage: Message = {
            id: `msg-${Date.now()}`,
            role: "user",
            content,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);

        // Simulate thinking steps
        setThinkingSteps([
            { id: "1", type: "thinking", title: "Understanding your question...", isActive: true },
        ]);

        setTimeout(() => {
            setThinkingSteps([
                { id: "1", type: "thinking", title: "Understanding your question...", isComplete: true },
                { id: "2", type: "searching", title: "Searching knowledge base...", isActive: true },
            ]);
        }, 500);

        setTimeout(() => {
            setThinkingSteps([
                { id: "1", type: "thinking", title: "Understanding your question...", isComplete: true },
                { id: "2", type: "searching", title: "Searching knowledge base...", isComplete: true },
                { id: "3", type: "analyzing", title: "Analyzing results...", isActive: true },
            ]);
        }, 1000);

        // Generate response based on content - with embedded widgets
        setTimeout(() => {
            setThinkingSteps([]);

            let responseContent = "";
            let widget: MessageWidget | undefined;
            const tokenSymbol = context?.tokenData?.tokenSymbol || "BULLA";

            // Check for natural language commands
            const addWatchlistMatch = content.match(COMMAND_PATTERNS.ADD_WATCHLIST);
            const showWatchlistMatch = content.match(COMMAND_PATTERNS.SHOW_WATCHLIST);
            const setAlertMatch = content.match(COMMAND_PATTERNS.SET_ALERT);
            const showWhaleActivityMatch = content.match(COMMAND_PATTERNS.SHOW_WHALE_ACTIVITY);
            const tradingSuggestionMatch = content.match(COMMAND_PATTERNS.TRADING_SUGGESTION);
            const showPortfolioMatch = content.match(COMMAND_PATTERNS.SHOW_PORTFOLIO);
            const captureChartMatch = content.match(COMMAND_PATTERNS.CAPTURE_CHART);
            const generateThreadMatch = content.match(COMMAND_PATTERNS.GENERATE_THREAD);

            if (addWatchlistMatch || (content.toLowerCase().includes("add") && content.toLowerCase().includes("watchlist"))) {
                // Add to watchlist command
                const token = addWatchlistMatch?.[1] || tokenSymbol;
                responseContent = `Done! ✅\n\nI've added ${token} to your watchlist.`;
                widget = {
                    type: "action_confirmation",
                    actionType: "watchlist_add",
                    tokenSymbol: token,
                    details: [
                        "Price change ±20%",
                        "Liquidity drop >10%",
                        "Whale movement >$50K",
                    ],
                };
                // Actually add to watchlist
                if (!watchlistTokens.find(t => t.symbol === token)) {
                    const newToken = {
                        id: `token-${Date.now()}`,
                        symbol: token,
                        name: token + " Token",
                        chain: context?.tokenData?.chain || "solana",
                        contractAddress: context?.tokenData?.pairAddress || "unknown",
                        price: context?.tokenData?.price || "$0.00001234",
                        priceChange24h: 156.7,
                        hasAlerts: true,
                        alertCount: 3,
                    };
                    setWatchlistTokens(prev => [...prev, newToken]);
                    setIsInWatchlist(true);
                }
            } else if (showWatchlistMatch || content.toLowerCase().includes("watchlist") && (content.toLowerCase().includes("show") || content.toLowerCase().includes("view"))) {
                // Show watchlist command
                responseContent = `Here's your watchlist:`;
                const watchlistItems: WatchlistItem[] = watchlistTokens.map(t => ({
                    id: t.id,
                    symbol: t.symbol,
                    name: t.name,
                    chain: t.chain,
                    price: t.price,
                    priceChange24h: t.priceChange24h,
                    alertCount: t.alertCount,
                }));
                widget = {
                    type: "watchlist",
                    tokens: watchlistItems,
                };
                if (watchlistTokens.length > 0) {
                    const bestPerformer = watchlistTokens.reduce((a, b) =>
                        a.priceChange24h > b.priceChange24h ? a : b
                    );
                    responseContent += `\n\n${bestPerformer.symbol} is up ${bestPerformer.priceChange24h.toFixed(1)}% - your best performer! Want me to analyze if it's time to take profits?`;
                }
            } else if (setAlertMatch || content.toLowerCase().includes("alert") && (content.toLowerCase().includes("set") || content.toLowerCase().includes("notify"))) {
                // Set alert command
                const match = content.match(/(\d+)%/);
                const percentage = match ? match[1] : "20";
                const direction = content.toLowerCase().includes("drop") ? "drops" : "changes";
                responseContent = `I'll set that up for you:`;
                widget = {
                    type: "alert_config",
                    config: {
                        tokenSymbol: tokenSymbol,
                        condition: `Price ${direction} ${percentage}%`,
                        currentPrice: context?.tokenData?.price || "$0.00001234",
                        triggerPrice: "$0.00000987",
                        channels: {
                            browser: true,
                            inApp: true,
                            email: false,
                        },
                    },
                    isNew: true,
                };
                responseContent += `\n\nDone! I'll notify you if ${tokenSymbol} ${direction} ${percentage}% from current price. Want to set any other alerts?`;
            } else if (content.toLowerCase().includes("safe") || content.toLowerCase().includes("rug") || content.toLowerCase().includes("analyze") || content.toLowerCase().includes("research")) {
                // Token analysis with embedded widget
                responseContent = `Here's my analysis of ${tokenSymbol}:`;
                widget = {
                    type: "token_analysis",
                    data: {
                        symbol: tokenSymbol,
                        name: context?.tokenData?.tokenName || "Bulla Token",
                        chain: context?.tokenData?.chain || "solana",
                        price: context?.tokenData?.price || "$0.00001234",
                        priceChange24h: 156.7,
                        marketCap: "$2.1M",
                        volume24h: "$1.2M",
                        liquidity: "$450K",
                        safetyScore: MOCK_SAFETY_SCORE,
                        holderCount: 12456,
                        top10HolderPercent: 35,
                    },
                    isInWatchlist: isInWatchlist,
                };
                responseContent += `\n\nBased on your moderate risk profile, suggested allocation: 2-5% of portfolio. The safety score of ${MOCK_SAFETY_SCORE}/100 indicates medium risk - proceed with caution.`;
            } else if (showWhaleActivityMatch || (content.toLowerCase().includes("whale") && (content.toLowerCase().includes("show") || content.toLowerCase().includes("activity")))) {
                // Show whale activity command (Epic 2)
                responseContent = `Here's recent whale activity for ${tokenSymbol}:`;
                widget = {
                    type: "whale_activity",
                    transactions: MOCK_WHALE_TRANSACTIONS.slice(0, 5), // Show top 5
                };
                responseContent += `\n\n🐋 I'm tracking 5 large transactions (>$10K) in the last hour. The smart money wallet 0x742d...35BA just bought $50K worth - this could be a bullish signal!`;
            } else if (tradingSuggestionMatch || (content.toLowerCase().includes("suggest") || content.toLowerCase().includes("entry") || content.toLowerCase().includes("exit"))) {
                // Trading suggestion command (Epic 3)
                const token = tradingSuggestionMatch?.[3] || tokenSymbol;
                responseContent = `Here's my trading analysis for ${token}:`;
                widget = {
                    type: "trading_suggestion",
                    suggestion: MOCK_TRADING_SUGGESTION,
                };
                responseContent += `\n\n📊 Based on technical analysis, I've identified optimal entry zones and profit targets. The risk/reward ratio of 1:3.3 looks favorable. Would you like me to set price alerts for these levels?`;
            } else if (showPortfolioMatch || (content.toLowerCase().includes("portfolio") && (content.toLowerCase().includes("show") || content.toLowerCase().includes("view")))) {
                // Show portfolio command (Epic 3)
                responseContent = `Here's your portfolio overview:`;
                widget = {
                    type: "portfolio",
                    portfolio: MOCK_PORTFOLIO,
                };
                responseContent += `\n\n💼 Your portfolio is up $234 (4.7%) in the last 24 hours! BULLA is your best performer at +15%. Want me to analyze if it's time to take profits?`;
            } else if (captureChartMatch || (content.toLowerCase().includes("capture") || content.toLowerCase().includes("screenshot")) && content.toLowerCase().includes("chart")) {
                // Capture chart command (Epic 4)
                responseContent = `I'll help you capture this chart:`;
                widget = {
                    type: "chart_capture",
                    metadata: {
                        tokenSymbol: tokenSymbol,
                        tokenName: context?.tokenData?.tokenName || "Bulla Token",
                        chain: context?.tokenData?.chain || "solana",
                        price: context?.tokenData?.price || "$0.00001234",
                        priceChange24h: 156.7,
                        volume24h: context?.tokenData?.volume24h || "$1.2M",
                        liquidity: context?.tokenData?.liquidity || "$450K",
                        timestamp: new Date(),
                    },
                };
                responseContent += `\n\n📸 I've prepared the chart capture tool with auto-filled metadata. Choose your style (dark/light/neon) and export format (Twitter/Telegram/Instagram). The metadata overlay will make your chart look professional!`;
            } else if (generateThreadMatch || (content.toLowerCase().includes("generate") || content.toLowerCase().includes("create")) && content.toLowerCase().includes("thread")) {
                // Generate thread command (Epic 4)
                responseContent = `I'll help you create a Twitter thread about ${tokenSymbol}:`;
                widget = {
                    type: "thread_generator",
                    tokenAddress: context?.tokenData?.pairAddress,
                    tokenSymbol: tokenSymbol,
                    chain: context?.tokenData?.chain || "solana",
                };
                responseContent += `\n\n🧵 I've prepared the thread generator with token info auto-filled. Choose your tone (bullish/neutral/bearish) and thread length (5-10 tweets). I'll generate a professional thread structure: Hook → Analysis → Implications → Conclusion. You can edit each tweet before posting!`;
            } else if (content.toLowerCase().includes("holder")) {
                responseContent = `**Holder Analysis for ${tokenSymbol}:**

📊 **Distribution:**
- Total Holders: 12,456
- Top 10 Holders: 35% of supply
- Top 50 Holders: 52% of supply

🐋 **Whale Activity (24h):**
- 3 large buys (>$10K each)
- 1 large sell ($25K)
- Net flow: +$15K

⚠️ **Concentration Risk:** Medium
The top holder owns 8.5% which is relatively high.`;
            } else {
                responseContent = `I can help you with crypto analysis! Try these commands:

**Epic 1: Basic Commands**
• **"Add BULLA to my watchlist"** - Track tokens
• **"Show my watchlist"** - View tracked tokens
• **"Set alert if BULLA drops 20%"** - Price alerts
• **"Analyze BULLA"** - Full token analysis
• **"Is BULLA safe?"** - Safety check

**Epic 2: Smart Monitoring**
• **"Show whale activity"** - Large transactions (>$10K)

**Epic 3: Trading Intelligence**
• **"Suggest entry for BULLA"** - Entry/exit suggestions
• **"Show my portfolio"** - Portfolio tracker with P&L

**Epic 4: Content Creation**
• **"Capture chart"** - Screenshot with metadata
• **"Generate thread"** - AI Twitter thread generator

What would you like to know?`;
            }

            const assistantMessage: Message = {
                id: `msg-${Date.now()}`,
                role: "assistant",
                content: responseContent,
                timestamp: new Date(),
                widget,
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setIsStreaming(false);
        }, 1500);
    };

    const handleSuggestionClick = (text: string) => {
        handleSendMessage(text);
    };

    const handleSpaceChange = (space: SearchSpace) => {
        setSelectedSpace(space);
    };

    const handleSettingsClick = (item: string) => {
        console.log("Settings item clicked:", item);
        if (item === "watchlist") {
            setViewMode("watchlist");
        }
    };

    const handleLogout = () => {
        console.log("Logout clicked");
    };

    const handleSafetyCheck = () => {
        setViewMode("safety");
    };

    const handleAddToWatchlist = () => {
        setIsInWatchlist(!isInWatchlist);
        if (!isInWatchlist && context?.tokenData) {
            const newToken = {
                id: `token-${Date.now()}`,
                symbol: context.tokenData.tokenSymbol || "TOKEN",
                name: context.tokenData.tokenName || "Unknown Token",
                chain: context.tokenData.chain,
                contractAddress: context.tokenData.pairAddress,
                price: context.tokenData.price || "$0",
                priceChange24h: context.tokenData.priceChange24h || 0,
                hasAlerts: false,
            };
            setWatchlistTokens(prev => [...prev, newToken]);
        }
    };

    const handleConfigureAlerts = (tokenSymbol: string) => {
        setSelectedTokenForAlert(tokenSymbol);
        setShowAlertModal(true);
    };

    const handleRugCheck = () => {
        handleSendMessage("Check this token for rug pull risks");
    };

    // Handle widget actions from embedded widgets in chat
    const handleWidgetAction = (action: string, data?: unknown) => {
        console.log("Widget action:", action, data);
        switch (action) {
            case "view_watchlist":
                handleSendMessage("Show my watchlist");
                break;
            case "edit_alerts":
                if (typeof data === "string") {
                    handleConfigureAlerts(data);
                }
                break;
            case "analyze_token":
                if (data && typeof data === "object" && "symbol" in data) {
                    handleSendMessage(`Analyze ${(data as { symbol: string }).symbol}`);
                }
                break;
            case "remove_from_watchlist":
                if (typeof data === "string") {
                    setWatchlistTokens(prev => prev.filter(t => t.id !== data));
                }
                break;
            case "add_to_watchlist":
                if (data && typeof data === "object" && "symbol" in data) {
                    handleSendMessage(`Add ${(data as { symbol: string }).symbol} to my watchlist`);
                }
                break;
            case "set_alert":
                if (typeof data === "string") {
                    handleConfigureAlerts(data);
                }
                break;
            case "analyze_further":
                if (data && typeof data === "object" && "symbol" in data) {
                    handleSendMessage(`Tell me more about ${(data as { symbol: string }).symbol} holders and whale activity`);
                }
                break;
            case "tell_more":
                if (data && typeof data === "object" && "tokenSymbol" in data) {
                    handleSendMessage(`Tell me more about ${(data as { tokenSymbol: string }).tokenSymbol}`);
                }
                break;
            default:
                console.log("Unhandled widget action:", action);
        }
    };

    // Quick suggestions based on context
    const quickSuggestions = context?.pageType === "dexscreener"
        ? ["Add to watchlist", "Is this safe?", "Set price alert"]
        : ["Show my watchlist", "What's trending?", "Analyze BULLA"];

    // Handle token search from header
    const handleTokenSearch = async (query: string) => {
        // Add user message
        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: `Analyze ${query}`,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);

        // Simulate AI response with token analysis
        setTimeout(() => {
            const aiMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `Searching for token: ${query}...`,
                timestamp: new Date(),
                widget: {
                    type: "token_analysis",
                    data: {
                        symbol: query.toUpperCase(),
                        name: `${query} Token`,
                        chain: "solana",
                        price: "$0.00001234",
                        priceChange24h: 156.7,
                        marketCap: "$2.1M",
                        volume24h: "$1.2M",
                        liquidity: "$450K",
                        safetyScore: MOCK_SAFETY_SCORE,
                        holderCount: 12456,
                        top10HolderPercent: 35,
                    },
                    isInWatchlist: false,
                },
            };
            setMessages((prev) => [...prev, aiMessage]);
        }, 500);
    };

    /**
     * Handle detected token click
     */
    const handleDetectedTokenClick = (token: TokenData) => {
        const query = token.tokenSymbol || token.pairAddress;
        handleTokenSearch(query);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header with space selector and settings */}
            <ChatHeader
                searchSpaces={MOCK_SEARCH_SPACES}
                selectedSpace={selectedSpace}
                onSpaceChange={handleSpaceChange}
                userName={userName}
                onSettingsClick={handleSettingsClick}
                onLogout={handleLogout}
                onTokenSearch={handleTokenSearch}
            />

            {/* Token info card (only on DexScreener) */}
            {context?.pageType === "dexscreener" && context.tokenData && viewMode === "chat" && (
                <TokenInfoCard
                    tokenData={context.tokenData}
                    isInWatchlist={isInWatchlist}
                    onAddToWatchlist={handleAddToWatchlist}
                    onSafetyCheck={handleSafetyCheck}
                    onRugCheck={handleRugCheck}
                />
            )}

            {/* Detected tokens list (on Twitter and other pages) */}
            {context?.detectedTokens && context.detectedTokens.length > 0 && viewMode === "chat" && (
                <DetectedTokensList
                    tokens={context.detectedTokens}
                    onTokenClick={handleDetectedTokenClick}
                />
            )}

            {/* Main content area */}
            <div className="flex-1 overflow-y-auto">
                {viewMode === "chat" && (
                    <>
                        <ChatMessages
                            messages={messages}
                            onSuggestionClick={handleSuggestionClick}
                            userName={userName}
                            onWidgetAction={handleWidgetAction}
                        />

                        {/* Thinking steps (shown during streaming) */}
                        {isStreaming && thinkingSteps.length > 0 && (
                            <div className="px-4 pb-4">
                                <ThinkingStepsDisplay
                                    steps={thinkingSteps}
                                    isThinking={isStreaming}
                                />
                            </div>
                        )}
                    </>
                )}

                {viewMode === "watchlist" && (
                    <WatchlistPanel
                        tokens={watchlistTokens}
                        recentAlerts={MOCK_WATCHLIST_ALERTS}
                        onTokenClick={(token) => console.log("Token clicked:", token)}
                        onRemoveToken={(id) => setWatchlistTokens(prev => prev.filter(t => t.id !== id))}
                        onAddToken={() => console.log("Add token clicked")}
                        onConfigureAlerts={(token) => handleConfigureAlerts(token.symbol)}
                        onAlertClick={(alert) => console.log("Alert clicked:", alert)}
                    />
                )}

                {viewMode === "safety" && (
                    <div className="p-4">
                        <SafetyScoreDisplay
                            score={MOCK_SAFETY_SCORE}
                            factors={MOCK_SAFETY_FACTORS}
                            sources={MOCK_SAFETY_SOURCES}
                            timestamp={new Date()}
                            tokenSymbol={context?.tokenData?.tokenSymbol}
                            isInWatchlist={isInWatchlist}
                            onAddToWatchlist={handleAddToWatchlist}
                            onSetAlert={() => handleConfigureAlerts(context?.tokenData?.tokenSymbol || "TOKEN")}
                        />
                        <button
                            className="mt-4 text-sm text-primary hover:underline"
                            onClick={() => setViewMode("chat")}
                        >
                            ← Back to chat
                        </button>
                    </div>
                )}
            </div>

            {/* Chat input and quick capture (only in chat mode) */}
            {viewMode === "chat" && (
                <div className="flex-shrink-0">
                    <ChatInput
                        onSend={handleSendMessage}
                        disabled={isStreaming}
                        placeholder={
                            context?.pageType === "dexscreener"
                                ? `Ask about ${context.tokenData?.tokenSymbol || "this token"}...`
                                : "Ask me anything..."
                        }
                        suggestions={messages.length === 0 ? [] : quickSuggestions}
                        onSuggestionClick={handleSuggestionClick}
                    />
                    <QuickCapture />
                </div>
            )}

            {/* Back to chat button for other views */}
            {viewMode !== "chat" && (
                <div className="flex-shrink-0 border-t p-3">
                    <button
                        className="w-full py-2 text-sm text-center text-primary hover:bg-primary/5 rounded-md transition-colors"
                        onClick={() => setViewMode("chat")}
                    >
                        ← Back to Chat
                    </button>
                </div>
            )}

            {/* Alert configuration modal */}
            <AlertConfigModal
                open={showAlertModal}
                onOpenChange={setShowAlertModal}
                tokenSymbol={selectedTokenForAlert || "TOKEN"}
                currentPrice={context?.tokenData?.price}
                onSave={(alerts) => {
                    console.log("Alerts saved:", alerts);
                    setShowAlertModal(false);
                }}
            />
        </div>
    );
}
