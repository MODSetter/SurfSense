import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    MessageSquare,
    Sparkles,
    Copy,
    Twitter,
    Edit2,
    Trash2,
    Plus,
    RefreshCw,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface Tweet {
    number: number;
    content: string;
    type: "hook" | "analysis" | "implication" | "conclusion" | "disclaimer";
    includeChart?: boolean;
}

export interface ThreadRequest {
    tokenAddress: string;
    tokenSymbol: string;
    chain: string;
    topic?: string;
    length: number;
    tone: "bullish" | "neutral" | "bearish";
}

export interface GeneratedThread {
    tweets: Tweet[];
    metadata: {
        tokenSymbol: string;
        keyStats: Record<string, any>;
    };
}

export interface ThreadGeneratorPanelProps {
    /** Current token info */
    tokenAddress?: string;
    tokenSymbol?: string;
    chain?: string;
    /** Callback when thread is generated */
    onGenerate?: (request: ThreadRequest) => void;
    /** Callback when thread is exported */
    onExport?: (format: "copy" | "twitter") => void;
    /** Additional class names */
    className?: string;
}

/**
 * ThreadGeneratorPanel - AI-powered Twitter thread generator
 *
 * Features:
 * - Auto-fill token info from current page
 * - Customizable thread length (5-10 tweets)
 * - Tone selection (bullish/neutral/bearish)
 * - AI-generated thread structure (Hook → Analysis → Implications → Conclusion)
 * - Edit individual tweets
 * - Reorder tweets
 * - Export options (copy all, tweet directly)
 */
export function ThreadGeneratorPanel({
    tokenAddress,
    tokenSymbol,
    chain,
    onGenerate,
    onExport,
    className,
}: ThreadGeneratorPanelProps) {
    const [request, setRequest] = useState<ThreadRequest>({
        tokenAddress: tokenAddress || "",
        tokenSymbol: tokenSymbol || "",
        chain: chain || "solana",
        topic: "",
        length: 7,
        tone: "bullish",
    });

    const [generatedThread, setGeneratedThread] = useState<GeneratedThread | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [editingTweet, setEditingTweet] = useState<number | null>(null);

    // Mock generated thread
    const mockThread: GeneratedThread = {
        tweets: [
            {
                number: 1,
                content: `🧵 ${request.tokenSymbol} is showing massive volume spike (+200%) in the last 24h. Here's what you need to know 👇`,
                type: "hook",
            },
            {
                number: 2,
                content: `Contract analysis:\n✅ Verified on-chain\n✅ Ownership renounced\n✅ LP locked for 90 days\n✅ No proxy contracts\n\nSolid fundamentals from a security perspective.`,
                type: "analysis",
            },
            {
                number: 3,
                content: `Holder distribution looks healthy:\n• 1,234 holders\n• Top 10 hold only 35%\n• No single whale dominance\n\nThis suggests organic growth and reduced rug pull risk.`,
                type: "analysis",
            },
            {
                number: 4,
                content: `Liquidity: $50K\nVolume/Liquidity ratio: 2.0x\n\nStrong trading activity relative to liquidity. This is a bullish signal for price discovery.`,
                type: "analysis",
            },
            {
                number: 5,
                content: `Social sentiment is turning positive:\n• 500 Twitter mentions (24h)\n• 1,200 Telegram messages\n• Growing community engagement\n\nMomentum is building.`,
                type: "implication",
            },
            {
                number: 6,
                content: `What this means:\n\nWe're seeing early signs of a potential breakout. Volume precedes price, and the fundamentals support sustained growth.`,
                type: "implication",
            },
            {
                number: 7,
                content: `TL;DR:\n✅ Verified & safe contract\n✅ Healthy holder distribution\n✅ Strong volume growth\n✅ Positive social sentiment\n\nDYOR, but this one's worth watching closely. 👀`,
                type: "conclusion",
            },
        ],
        metadata: {
            tokenSymbol: request.tokenSymbol,
            keyStats: {
                price: 0.0001234,
                change24h: 15.5,
                volume: 100000,
                liquidity: 50000,
            },
        },
    };

    const handleGenerate = async () => {
        setIsGenerating(true);
        await onGenerate?.(request);
        // Mock: simulate generation
        setTimeout(() => {
            setGeneratedThread(mockThread);
            setIsGenerating(false);
        }, 2000);
    };

    const handleEditTweet = (number: number, newContent: string) => {
        if (!generatedThread) return;
        const updatedTweets = generatedThread.tweets.map((tweet) =>
            tweet.number === number ? { ...tweet, content: newContent } : tweet
        );
        setGeneratedThread({ ...generatedThread, tweets: updatedTweets });
        setEditingTweet(null);
    };

    const handleDeleteTweet = (number: number) => {
        if (!generatedThread) return;
        const updatedTweets = generatedThread.tweets
            .filter((tweet) => tweet.number !== number)
            .map((tweet, index) => ({ ...tweet, number: index + 1 }));
        setGeneratedThread({ ...generatedThread, tweets: updatedTweets });
    };

    const handleAddTweet = () => {
        if (!generatedThread) return;
        const newTweet: Tweet = {
            number: generatedThread.tweets.length + 1,
            content: "New tweet content...",
            type: "analysis",
        };
        setGeneratedThread({
            ...generatedThread,
            tweets: [...generatedThread.tweets, newTweet],
        });
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <MessageSquare className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">AI Thread Generator</h2>
                        <p className="text-xs text-muted-foreground">
                            Create Twitter threads with AI
                        </p>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {!generatedThread ? (
                    <>
                        {/* Input Form */}
                        <div className="space-y-3">
                            {/* Token Info */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Token</label>
                                <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
                                    <span className="font-semibold">{request.tokenSymbol || "Not selected"}</span>
                                    {request.chain && <ChainIcon chain={request.chain} size="xs" />}
                                </div>
                            </div>

                            {/* Topic */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Topic (Optional)</label>
                                <input
                                    type="text"
                                    placeholder="Auto-generate from token data"
                                    value={request.topic}
                                    onChange={(e) => setRequest({ ...request, topic: e.target.value })}
                                    className="w-full p-2 text-sm border rounded"
                                />
                            </div>

                            {/* Length */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Length</label>
                                <select
                                    value={request.length}
                                    onChange={(e) => setRequest({ ...request, length: parseInt(e.target.value) })}
                                    className="w-full p-2 text-sm border rounded"
                                >
                                    {[5, 6, 7, 8, 9, 10].map((len) => (
                                        <option key={len} value={len}>
                                            {len} tweets
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Tone */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Tone</label>
                                <div className="flex gap-2">
                                    {(["bullish", "neutral", "bearish"] as const).map((tone) => (
                                        <button
                                            key={tone}
                                            className={cn(
                                                "flex-1 p-2 rounded border text-xs font-medium transition-colors",
                                                request.tone === tone
                                                    ? "bg-primary text-primary-foreground border-primary"
                                                    : "bg-muted hover:bg-muted/80"
                                            )}
                                            onClick={() => setRequest({ ...request, tone })}
                                        >
                                            {tone.charAt(0).toUpperCase() + tone.slice(1)}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Generate Button */}
                        <Button
                            variant="default"
                            className="w-full"
                            onClick={handleGenerate}
                            disabled={isGenerating || !request.tokenSymbol}
                        >
                            <Sparkles className="h-4 w-4 mr-2" />
                            {isGenerating ? "Generating..." : "Generate Thread"}
                        </Button>
                    </>
                ) : (
                    <>
                        {/* Generated Thread Preview */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <h3 className="font-semibold text-sm">Preview</h3>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setGeneratedThread(null)}
                                >
                                    <RefreshCw className="h-3 w-3 mr-1" />
                                    Regenerate
                                </Button>
                            </div>

                            {/* Tweets */}
                            <div className="space-y-2">
                                {generatedThread.tweets.map((tweet) => (
                                    <div
                                        key={tweet.number}
                                        className="p-3 border rounded-lg bg-background"
                                    >
                                        {editingTweet === tweet.number ? (
                                            <div className="space-y-2">
                                                <textarea
                                                    value={tweet.content}
                                                    onChange={(e) =>
                                                        handleEditTweet(tweet.number, e.target.value)
                                                    }
                                                    className="w-full p-2 text-sm border rounded min-h-[80px]"
                                                />
                                                <div className="flex gap-2">
                                                    <Button
                                                        variant="default"
                                                        size="sm"
                                                        onClick={() => setEditingTweet(null)}
                                                    >
                                                        Save
                                                    </Button>
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setEditingTweet(null)}
                                                    >
                                                        Cancel
                                                    </Button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <div className="flex items-start justify-between mb-2">
                                                    <span className="text-xs font-semibold text-muted-foreground">
                                                        {tweet.number}/{generatedThread.tweets.length}
                                                    </span>
                                                    <div className="flex gap-1">
                                                        <button
                                                            className="p-1 hover:bg-muted rounded"
                                                            onClick={() => setEditingTweet(tweet.number)}
                                                        >
                                                            <Edit2 className="h-3 w-3" />
                                                        </button>
                                                        <button
                                                            className="p-1 hover:bg-muted rounded"
                                                            onClick={() => handleDeleteTweet(tweet.number)}
                                                        >
                                                            <Trash2 className="h-3 w-3" />
                                                        </button>
                                                    </div>
                                                </div>
                                                <p className="text-sm whitespace-pre-wrap">{tweet.content}</p>
                                            </>
                                        )}
                                    </div>
                                ))}
                            </div>

                            {/* Add Tweet Button */}
                            <Button
                                variant="outline"
                                className="w-full"
                                onClick={handleAddTweet}
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Add Tweet
                            </Button>
                        </div>
                    </>
                )}
            </div>

            {/* Footer - Export Options */}
            {generatedThread && (
                <div className="border-t p-3 space-y-2">
                    <Button
                        variant="default"
                        className="w-full"
                        onClick={() => onExport?.("copy")}
                    >
                        <Copy className="h-4 w-4 mr-2" />
                        Copy All Tweets
                    </Button>
                    <Button
                        variant="outline"
                        className="w-full"
                        onClick={() => onExport?.("twitter")}
                    >
                        <Twitter className="h-4 w-4 mr-2" />
                        Tweet Now
                    </Button>
                </div>
            )}
        </div>
    );
}

