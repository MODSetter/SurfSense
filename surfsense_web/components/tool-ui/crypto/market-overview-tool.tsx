"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { BarChart3, TrendingUp, TrendingDown, Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Schema for market token
const MarketTokenSchema = z.object({
    symbol: z.string(),
    name: z.string(),
    price: z.number(),
    priceChange24h: z.number(),
    marketCap: z.number().optional(),
    volume24h: z.number().optional(),
});

// Schema for market overview tool arguments
export const MarketOverviewArgsSchema = z.object({
    tokens: z.array(MarketTokenSchema),
    totalMarketCap: z.number().optional(),
    totalVolume24h: z.number().optional(),
    btcDominance: z.number().optional(),
    fearGreedIndex: z.number().optional(),
});

export type MarketOverviewArgs = z.infer<typeof MarketOverviewArgsSchema>;

// Schema for market overview result
export const MarketOverviewResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type MarketOverviewResult = z.infer<typeof MarketOverviewResultSchema>;

const formatPrice = (price: number): string => {
    if (price < 1) return `$${price.toFixed(4)}`;
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number): string => {
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    return `$${num.toFixed(2)}`;
};

/**
 * MarketOverviewToolUI - Displays market overview inline in chat
 * Used when AI responds to "show market overview" or "how's the market?"
 */
export const MarketOverviewToolUI = makeAssistantToolUI<MarketOverviewArgs, MarketOverviewResult>({
    toolName: "get_market_overview",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const tokens = args.tokens || [];

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Globe className="h-5 w-5 text-blue-500" />
                        Market Overview
                        {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Global Stats */}
                    {(args.totalMarketCap || args.btcDominance || args.fearGreedIndex) && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {args.totalMarketCap && (
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground">Total Market Cap</p>
                                    <p className="font-medium">{formatLargeNumber(args.totalMarketCap)}</p>
                                </div>
                            )}
                            {args.totalVolume24h && (
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground">24h Volume</p>
                                    <p className="font-medium">{formatLargeNumber(args.totalVolume24h)}</p>
                                </div>
                            )}
                            {args.btcDominance && (
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground">BTC Dominance</p>
                                    <p className="font-medium">{args.btcDominance.toFixed(1)}%</p>
                                </div>
                            )}
                            {args.fearGreedIndex && (
                                <div className={cn("rounded-lg p-3", args.fearGreedIndex > 50 ? "bg-green-500/10" : "bg-red-500/10")}>
                                    <p className="text-xs text-muted-foreground">Fear & Greed</p>
                                    <p className={cn("font-medium", args.fearGreedIndex > 50 ? "text-green-500" : "text-red-500")}>
                                        {args.fearGreedIndex} - {args.fearGreedIndex > 75 ? "Extreme Greed" : args.fearGreedIndex > 50 ? "Greed" : args.fearGreedIndex > 25 ? "Fear" : "Extreme Fear"}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Token Prices */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {tokens.map((token) => (
                            <div key={token.symbol} className="bg-muted/50 rounded-lg p-4 flex items-center justify-between">
                                <div>
                                    <p className="font-bold text-lg">{token.symbol}</p>
                                    <p className="text-xs text-muted-foreground">{token.name}</p>
                                </div>
                                <div className="text-right">
                                    <p className="font-medium">{formatPrice(token.price)}</p>
                                    <p className={cn("text-sm flex items-center justify-end gap-0.5", token.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                        {token.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                        {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(2)}%
                                    </p>
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    },
});

