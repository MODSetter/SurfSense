"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Shield, TrendingUp, TrendingDown, Users, AlertTriangle, Star, Bell, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";
import { SafetyBadge } from "@/components/crypto/SafetyBadge";

// Schema for token analysis tool arguments
export const TokenAnalysisArgsSchema = z.object({
    symbol: z.string(),
    name: z.string().optional(),
    chain: z.string(),
    contractAddress: z.string().optional(),
    price: z.number(),
    priceChange24h: z.number(),
    marketCap: z.number().optional(),
    volume24h: z.number().optional(),
    liquidity: z.number().optional(),
    safetyScore: z.number().optional(),
    holderCount: z.number().optional(),
    top10HolderPercent: z.number().optional(),
});

export type TokenAnalysisArgs = z.infer<typeof TokenAnalysisArgsSchema>;

// Schema for token analysis result
export const TokenAnalysisResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
    isInWatchlist: z.boolean().optional(),
});

export type TokenAnalysisResult = z.infer<typeof TokenAnalysisResultSchema>;

const formatPrice = (price: number): string => {
    if (price < 0.00001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number): string => {
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

/**
 * TokenAnalysisToolUI - Displays comprehensive token analysis in chat
 * Used when AI responds to token research queries like "analyze BULLA" or "is BULLA safe?"
 */
export const TokenAnalysisToolUI = makeAssistantToolUI<TokenAnalysisArgs, TokenAnalysisResult>({
    toolName: "analyze_token",
    render: ({ args, result, status }) => {
        const isLoading = status.type === "running";
        const isInWatchlist = result?.isInWatchlist ?? false;

        const handleOpenDexScreener = () => {
            if (args.contractAddress) {
                window.open(`https://dexscreener.com/${args.chain}/${args.contractAddress}`, "_blank");
            }
        };

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <span>📊</span>
                        Token Analysis
                        {isLoading && <Badge variant="secondary" className="animate-pulse">Analyzing...</Badge>}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Token Header */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <ChainIcon chain={args.chain} size="md" />
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="font-bold text-lg">{args.symbol}</span>
                                    {args.name && <span className="text-muted-foreground text-sm">{args.name}</span>}
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="font-medium">{formatPrice(args.price)}</span>
                                    <span className={cn(
                                        "flex items-center gap-0.5 text-sm font-medium",
                                        args.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                                    )}>
                                        {args.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                        {args.priceChange24h >= 0 ? "+" : ""}{args.priceChange24h.toFixed(2)}%
                                    </span>
                                </div>
                            </div>
                        </div>
                        {args.safetyScore !== undefined && (
                            <SafetyBadge score={args.safetyScore} size="lg" />
                        )}
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {args.marketCap && (
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Market Cap</p>
                                <p className="font-medium">{formatLargeNumber(args.marketCap)}</p>
                            </div>
                        )}
                        {args.volume24h && (
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">24h Volume</p>
                                <p className="font-medium">{formatLargeNumber(args.volume24h)}</p>
                            </div>
                        )}
                        {args.liquidity && (
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Liquidity</p>
                                <p className="font-medium">{formatLargeNumber(args.liquidity)}</p>
                            </div>
                        )}
                        {args.holderCount && (
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Holders</p>
                                <p className="font-medium flex items-center gap-1">
                                    <Users className="h-3 w-3" />
                                    {args.holderCount.toLocaleString()}
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Holder Concentration Warning */}
                    {args.top10HolderPercent && args.top10HolderPercent > 50 && (
                        <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 text-sm bg-yellow-500/10 rounded-lg p-2">
                            <AlertTriangle className="h-4 w-4" />
                            <span>Top 10 holders own {args.top10HolderPercent}% of supply - high concentration risk</span>
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-2">
                        <Button variant="outline" size="sm" className="flex-1">
                            <Star className={cn("h-4 w-4 mr-2", isInWatchlist && "fill-yellow-500 text-yellow-500")} />
                            {isInWatchlist ? "In Watchlist" : "Add to Watchlist"}
                        </Button>
                        <Button variant="outline" size="sm">
                            <Bell className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleOpenDexScreener}>
                            <ExternalLink className="h-4 w-4" />
                        </Button>
                    </div>
                </CardContent>
            </Card>
        );
    },
});

