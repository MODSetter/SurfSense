"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Star, TrendingUp, TrendingDown, Bell, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for watchlist token
const WatchlistTokenSchema = z.object({
    id: z.string(),
    symbol: z.string(),
    name: z.string(),
    chain: z.string(),
    price: z.number(),
    priceChange24h: z.number(),
    alertCount: z.number().optional(),
});

// Schema for watchlist display tool arguments
export const WatchlistDisplayArgsSchema = z.object({
    tokens: z.array(WatchlistTokenSchema),
});

export type WatchlistDisplayArgs = z.infer<typeof WatchlistDisplayArgsSchema>;

// Schema for watchlist display result
export const WatchlistDisplayResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type WatchlistDisplayResult = z.infer<typeof WatchlistDisplayResultSchema>;

const formatPrice = (price: number): string => {
    if (price < 0.00001) return `$${price.toExponential(2)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * WatchlistDisplayToolUI - Displays user's watchlist inline in chat
 * Used when AI responds to "show my watchlist" or similar commands
 */
export const WatchlistDisplayToolUI = makeAssistantToolUI<WatchlistDisplayArgs, WatchlistDisplayResult>({
    toolName: "show_watchlist",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const tokens = args.tokens || [];

        if (tokens.length === 0) {
            return (
                <Card className="my-3">
                    <CardContent className="py-8 text-center">
                        <Star className="h-12 w-12 mx-auto text-muted-foreground/50 mb-3" />
                        <p className="text-muted-foreground">Your watchlist is empty</p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Say "Add [token] to my watchlist" to start tracking
                        </p>
                    </CardContent>
                </Card>
            );
        }

        // Find best and worst performers
        const sortedByChange = [...tokens].sort((a, b) => b.priceChange24h - a.priceChange24h);
        const bestPerformer = sortedByChange[0];
        const worstPerformer = sortedByChange[sortedByChange.length - 1];

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Star className="h-5 w-5 text-yellow-500" />
                            Your Watchlist
                            <Badge variant="secondary">{tokens.length}</Badge>
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                        <Button variant="outline" size="sm">
                            <Plus className="h-4 w-4 mr-1" />
                            Add Token
                        </Button>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                    {/* Token List */}
                    <div className="divide-y">
                        {tokens.map((token) => (
                            <div
                                key={token.id}
                                className="flex items-center justify-between py-3 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <ChainIcon chain={token.chain} size="sm" />
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium">{token.symbol}</span>
                                            {token.alertCount && token.alertCount > 0 && (
                                                <Badge variant="outline" className="text-xs px-1.5 py-0">
                                                    <Bell className="h-2.5 w-2.5 mr-0.5" />
                                                    {token.alertCount}
                                                </Badge>
                                            )}
                                        </div>
                                        <span className="text-xs text-muted-foreground">{token.name}</span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <div className="text-right">
                                        <p className="font-medium">{formatPrice(token.price)}</p>
                                        <p className={cn(
                                            "text-sm flex items-center justify-end gap-0.5",
                                            token.priceChange24h >= 0 ? "text-green-500" : "text-red-500"
                                        )}>
                                            {token.priceChange24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                                            {token.priceChange24h >= 0 ? "+" : ""}{token.priceChange24h.toFixed(1)}%
                                        </p>
                                    </div>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-red-500">
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Summary */}
                    {tokens.length > 1 && (
                        <div className="pt-3 border-t text-sm text-muted-foreground">
                            <span className="text-green-500 font-medium">{bestPerformer.symbol}</span> is your best performer (+{bestPerformer.priceChange24h.toFixed(1)}%)
                            {worstPerformer.priceChange24h < 0 && (
                                <span> • <span className="text-red-500 font-medium">{worstPerformer.symbol}</span> needs attention ({worstPerformer.priceChange24h.toFixed(1)}%)</span>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    },
});

