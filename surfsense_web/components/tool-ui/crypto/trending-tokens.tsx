"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Flame, TrendingUp, TrendingDown, Star, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for trending token
const TrendingTokenSchema = z.object({
    symbol: z.string(),
    name: z.string(),
    chain: z.string(),
    contractAddress: z.string().optional(),
    price: z.number(),
    priceChange24h: z.number(),
    priceChange1h: z.number().optional(),
    volume24h: z.number().optional(),
    liquidity: z.number().optional(),
    rank: z.number().optional(),
});

// Schema for trending tokens tool arguments
export const TrendingTokensArgsSchema = z.object({
    chain: z.string().optional(),
    tokens: z.array(TrendingTokenSchema),
    timeframe: z.string().optional(),
});

export type TrendingTokensArgs = z.infer<typeof TrendingTokensArgsSchema>;

// Schema for trending tokens result
export const TrendingTokensResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type TrendingTokensResult = z.infer<typeof TrendingTokensResultSchema>;

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
 * TrendingTokensToolUI - Displays trending/hot tokens inline in chat
 * Used when AI responds to "what's hot on Solana?" or "show trending tokens"
 */
export const TrendingTokensToolUI = makeAssistantToolUI<TrendingTokensArgs, TrendingTokensResult>({
    toolName: "get_trending_tokens",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const tokens = args.tokens || [];
        const chain = args.chain || "all chains";
        const timeframe = args.timeframe || "24h";

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Flame className="h-5 w-5 text-orange-500" />
                            Trending on {chain}
                            <Badge variant="secondary">{timeframe}</Badge>
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                    {tokens.length === 0 ? (
                        <p className="text-muted-foreground text-center py-4">No trending tokens found</p>
                    ) : (
                        <div className="divide-y">
                            {tokens.map((token, index) => (
                                <div key={token.symbol + index} className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer transition-colors">
                                    <div className="flex items-center gap-3">
                                        <span className="text-lg font-bold text-muted-foreground w-6">#{token.rank || index + 1}</span>
                                        <ChainIcon chain={token.chain} size="sm" />
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium">{token.symbol}</span>
                                            </div>
                                            <span className="text-xs text-muted-foreground">{token.name}</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="text-right">
                                            <p className="font-medium">{formatPrice(token.price)}</p>
                                            <p className={cn("text-sm flex items-center justify-end gap-0.5", token.priceChange24h >= 0 ? "text-green-500" : "text-red-500")}>
                                                {token.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                                {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(1)}%
                                            </p>
                                        </div>
                                        {token.volume24h && (
                                            <div className="text-right hidden md:block">
                                                <p className="text-xs text-muted-foreground">Volume</p>
                                                <p className="text-sm">{formatLargeNumber(token.volume24h)}</p>
                                            </div>
                                        )}
                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                            <Star className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    },
});

