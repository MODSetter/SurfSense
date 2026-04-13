import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    TrendingUp,
    TrendingDown,
    CheckCircle,
    XCircle,
    AlertTriangle,
    RefreshCw,
    ExternalLink,
    Shield,
    Users,
    Droplet,
    BarChart3,
    MessageSquare,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface TokenAnalysisData {
    tokenAddress: string;
    tokenSymbol: string;
    tokenName: string;
    chain: string;
    timestamp: Date;
    
    contract: {
        verified: boolean;
        renounced: boolean;
        isProxy: boolean;
        sourceCode: boolean;
    };
    
    holders: {
        count: number;
        top10Percent: number;
        distribution: { address: string; percent: number }[];
    };
    
    liquidity: {
        totalUSD: number;
        lpLocked: boolean;
        lpLockDuration?: number;
        liquidityMcapRatio: number;
    };
    
    volume: {
        volume24h: number;
        trend: "increasing" | "decreasing" | "stable";
        volumeLiquidityRatio: number;
    };
    
    price: {
        current: number;
        ath: number;
        atl: number;
        change7d: number;
        change30d: number;
        volatility: number;
    };
    
    social: {
        twitterMentions: number;
        telegramActivity: number;
        redditDiscussions: number;
        sentimentScore: number; // -1 to 1
        sentiment: "positive" | "negative" | "neutral";
    };
    
    aiSummary: string;
    recommendation: "buy" | "hold" | "sell" | "avoid";
    confidence: number; // 0-100
}

export interface TokenAnalysisPanelProps {
    /** Token analysis data */
    analysis: TokenAnalysisData;
    /** Callback when refresh is clicked */
    onRefresh?: () => void;
    /** Callback when "View Full Report" is clicked */
    onViewFullReport?: () => void;
    /** Whether data is loading */
    isLoading?: boolean;
    /** Additional class names */
    className?: string;
}

/**
 * TokenAnalysisPanel - Comprehensive token analysis display
 *
 * Features:
 * - AI-generated summary with recommendation
 * - Contract analysis (verified, renounced, proxy)
 * - Holder distribution analysis
 * - Liquidity analysis with LP lock status
 * - Volume trends and trading activity
 * - Price history and volatility
 * - Social sentiment analysis
 */
export function TokenAnalysisPanel({
    analysis,
    onRefresh,
    onViewFullReport,
    isLoading = false,
    className,
}: TokenAnalysisPanelProps) {
    const [isRefreshing, setIsRefreshing] = useState(false);

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh?.();
        setTimeout(() => setIsRefreshing(false), 1000);
    };

    const formatTimeAgo = (date: Date) => {
        const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        return `${Math.floor(minutes / 60)}h ago`;
    };

    const formatCurrency = (value: number) => {
        if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
        if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
        return `$${value.toFixed(0)}`;
    };

    const getRecommendationColor = (rec: string) => {
        switch (rec) {
            case "buy": return "text-green-600 dark:text-green-400";
            case "hold": return "text-yellow-600 dark:text-yellow-400";
            case "sell": return "text-orange-600 dark:text-orange-400";
            case "avoid": return "text-red-600 dark:text-red-400";
            default: return "text-muted-foreground";
        }
    };

    const getSentimentEmoji = (sentiment: string) => {
        switch (sentiment) {
            case "positive": return "😊";
            case "negative": return "😟";
            case "neutral": return "😐";
            default: return "🤔";
        }
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">Token Analysis</h2>
                        <p className="text-xs text-muted-foreground">
                            {analysis.tokenSymbol} • <ChainIcon chain={analysis.chain} size="xs" className="inline" />
                        </p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleRefresh}
                    disabled={isRefreshing}
                >
                    <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
                </Button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* AI Summary */}
                <div className="p-4 bg-primary/5 rounded-lg border border-primary/20">
                    <div className="flex items-start gap-2 mb-2">
                        <div className="text-lg">🤖</div>
                        <div className="flex-1">
                            <h3 className="font-semibold text-sm mb-1">AI Summary</h3>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {analysis.aiSummary}
                            </p>
                        </div>
                    </div>

                    {/* Recommendation */}
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-primary/10">
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">Recommendation:</span>
                            <span className={cn("font-bold text-sm uppercase", getRecommendationColor(analysis.recommendation))}>
                                {analysis.recommendation}
                            </span>
                        </div>
                        <div className="flex items-center gap-1">
                            <span className="text-xs text-muted-foreground">Confidence:</span>
                            <span className="font-semibold text-sm">{analysis.confidence}%</span>
                        </div>
                    </div>
                </div>

                {/* Contract Analysis */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Contract</h3>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
                            {analysis.contract.verified ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                                <XCircle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="text-xs">Verified</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
                            {analysis.contract.renounced ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                                <XCircle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="text-xs">Renounced</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
                            {!analysis.contract.isProxy ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                            )}
                            <span className="text-xs">{analysis.contract.isProxy ? "Proxy" : "Direct"}</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
                            {analysis.contract.sourceCode ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                                <XCircle className="h-4 w-4 text-red-600" />
                            )}
                            <span className="text-xs">Source Code</span>
                        </div>
                    </div>
                </div>

                {/* Holder Distribution */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Holders</h3>
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between p-2 bg-muted/50 rounded">
                            <span className="text-xs text-muted-foreground">Total Holders</span>
                            <span className="font-semibold text-sm">{analysis.holders.count.toLocaleString()}</span>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-muted/50 rounded">
                            <span className="text-xs text-muted-foreground">Top 10 Holdings</span>
                            <span className={cn(
                                "font-semibold text-sm",
                                analysis.holders.top10Percent > 50 ? "text-red-600" :
                                analysis.holders.top10Percent > 30 ? "text-yellow-600" :
                                "text-green-600"
                            )}>
                                {analysis.holders.top10Percent}%
                            </span>
                        </div>
                    </div>
                </div>

                {/* Liquidity */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Droplet className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Liquidity</h3>
                    </div>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between p-2 bg-muted/50 rounded">
                            <span className="text-xs text-muted-foreground">Total Liquidity</span>
                            <span className="font-semibold text-sm">{formatCurrency(analysis.liquidity.totalUSD)}</span>
                        </div>
                        <div className="flex items-center justify-between p-2 bg-muted/50 rounded">
                            <span className="text-xs text-muted-foreground">LP Lock Status</span>
                            <div className="flex items-center gap-1">
                                {analysis.liquidity.lpLocked ? (
                                    <>
                                        <CheckCircle className="h-3 w-3 text-green-600" />
                                        <span className="font-semibold text-xs text-green-600">
                                            {analysis.liquidity.lpLockDuration ? `${analysis.liquidity.lpLockDuration}d` : "Locked"}
                                        </span>
                                    </>
                                ) : (
                                    <>
                                        <XCircle className="h-3 w-3 text-red-600" />
                                        <span className="font-semibold text-xs text-red-600">Unlocked</span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Volume & Price */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <h3 className="font-semibold text-xs text-muted-foreground">Volume 24h</h3>
                        <div className="flex items-center gap-2">
                            <span className="font-bold text-lg">{formatCurrency(analysis.volume.volume24h)}</span>
                            {analysis.volume.trend === "increasing" ? (
                                <TrendingUp className="h-4 w-4 text-green-600" />
                            ) : analysis.volume.trend === "decreasing" ? (
                                <TrendingDown className="h-4 w-4 text-red-600" />
                            ) : null}
                        </div>
                    </div>
                    <div className="space-y-2">
                        <h3 className="font-semibold text-xs text-muted-foreground">Price</h3>
                        <div className="space-y-1">
                            <div className="font-bold text-lg">${analysis.price.current.toFixed(8)}</div>
                            <div className="flex gap-2 text-xs">
                                <span className={cn(
                                    analysis.price.change7d >= 0 ? "text-green-600" : "text-red-600"
                                )}>
                                    7d: {analysis.price.change7d >= 0 ? "+" : ""}{analysis.price.change7d.toFixed(1)}%
                                </span>
                                <span className={cn(
                                    analysis.price.change30d >= 0 ? "text-green-600" : "text-red-600"
                                )}>
                                    30d: {analysis.price.change30d >= 0 ? "+" : ""}{analysis.price.change30d.toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Social Sentiment */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Social Sentiment</h3>
                    </div>
                    <div className="p-3 bg-muted/50 rounded">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">
                                {getSentimentEmoji(analysis.social.sentiment)} {analysis.social.sentiment.charAt(0).toUpperCase() + analysis.social.sentiment.slice(1)}
                            </span>
                            <span className="text-xs text-muted-foreground">
                                Score: {(analysis.social.sentimentScore * 100).toFixed(0)}
                            </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                            <div>
                                <div className="text-muted-foreground">Twitter</div>
                                <div className="font-semibold">{analysis.social.twitterMentions}</div>
                            </div>
                            <div>
                                <div className="text-muted-foreground">Telegram</div>
                                <div className="font-semibold">{analysis.social.telegramActivity}</div>
                            </div>
                            <div>
                                <div className="text-muted-foreground">Reddit</div>
                                <div className="font-semibold">{analysis.social.redditDiscussions}</div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Last Updated */}
                <div className="text-xs text-muted-foreground text-center">
                    Last updated: {formatTimeAgo(analysis.timestamp)}
                </div>
            </div>

            {/* Footer */}
            <div className="border-t p-3">
                <Button
                    variant="default"
                    className="w-full"
                    onClick={onViewFullReport}
                >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    View Full Report
                </Button>
            </div>
        </div>
    );
}

