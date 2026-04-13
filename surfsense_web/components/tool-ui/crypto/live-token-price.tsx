"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, ExternalLink, Zap, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for live token price tool arguments
export const LiveTokenPriceArgsSchema = z.object({
    chain: z.string(),
    token_address: z.string(),
    token_symbol: z.string().optional(),
});

export type LiveTokenPriceArgs = z.infer<typeof LiveTokenPriceArgsSchema>;

// Schema for live token price result (matches backend response)
export const LiveTokenPriceResultSchema = z.object({
    id: z.string(),
    kind: z.literal("live_token_price"),
    chain: z.string(),
    token_address: z.string(),
    token_symbol: z.string().optional(),
    token_name: z.string().optional(),
    price_usd: z.string().optional(),
    price_native: z.string().optional(),
    price_change_5m: z.number().optional(),
    price_change_1h: z.number().optional(),
    price_change_6h: z.number().optional(),
    price_change_24h: z.number().optional(),
    volume_24h: z.number().optional(),
    liquidity_usd: z.number().optional(),
    market_cap: z.number().optional(),
    fdv: z.number().optional(),
    dex: z.string().optional(),
    pair_url: z.string().optional(),
    total_pairs: z.number().optional(),
    data_source: z.string().optional(),
    error: z.string().optional(),
});

export type LiveTokenPriceResult = z.infer<typeof LiveTokenPriceResultSchema>;

const formatPrice = (price: string | undefined): string => {
    if (!price || price === "N/A") return "N/A";
    const num = parseFloat(price);
    if (isNaN(num)) return price;
    if (num < 0.00001) return `$${num.toExponential(2)}`;
    if (num < 1) return `$${num.toFixed(6)}`;
    return `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number | undefined): string => {
    if (num === undefined || num === null) return "N/A";
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

const PriceChange = ({ value, label }: { value: number | undefined; label: string }) => {
    if (value === undefined || value === null) return null;
    const isPositive = value >= 0;
    return (
        <div className="text-center">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className={cn("text-sm font-medium", isPositive ? "text-green-500" : "text-red-500")}>
                {isPositive ? "+" : ""}{value.toFixed(2)}%
            </p>
        </div>
    );
};

/**
 * LiveTokenPriceToolUI - Displays real-time token price from DexScreener
 * Used when AI fetches current/live price data
 */
export const LiveTokenPriceToolUI = makeAssistantToolUI<LiveTokenPriceArgs, LiveTokenPriceResult>({
    toolName: "get_live_token_price",
    render: ({ args, result, status }) => {
        const isLoading = status.type === "running";
        const hasError = result?.error;

        const handleOpenDexScreener = () => {
            if (result?.pair_url) {
                window.open(result.pair_url, "_blank");
            } else if (args.token_address) {
                window.open(`https://dexscreener.com/${args.chain}/${args.token_address}`, "_blank");
            }
        };

        return (
            <Card className="my-3 overflow-hidden border-blue-500/20">
                <CardHeader className="pb-3 bg-gradient-to-r from-blue-500/5 to-transparent">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Zap className="h-5 w-5 text-blue-500" />
                        Live Price
                        {isLoading && <Badge variant="secondary" className="animate-pulse">Fetching...</Badge>}
                        {!isLoading && !hasError && (
                            <Badge variant="outline" className="text-xs text-blue-500 border-blue-500/30">
                                <RefreshCw className="h-3 w-3 mr-1" />
                                Real-time
                            </Badge>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-4">
                    {hasError ? (
                        <div className="text-red-500 text-sm p-3 bg-red-500/10 rounded-lg">
                            ⚠️ {result.error}
                        </div>
                    ) : (
                        <>
                            {/* Token Header */}
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <ChainIcon chain={result?.chain || args.chain} size="md" />
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-xl">
                                                {result?.token_symbol || args.token_symbol || "Token"}
                                            </span>
                                            {result?.token_name && (
                                                <span className="text-muted-foreground text-sm">{result.token_name}</span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-2xl">{formatPrice(result?.price_usd)}</span>
                                            {result?.price_change_24h !== undefined && (
                                                <span className={cn(
                                                    "flex items-center gap-0.5 text-sm font-medium",
                                                    result.price_change_24h >= 0 ? "text-green-500" : "text-red-500"
                                                )}>
                                                    {result.price_change_24h >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                                                    {result.price_change_24h >= 0 ? "+" : ""}{result.price_change_24h.toFixed(2)}%
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Price Changes */}
                            <div className="flex justify-around py-2 bg-muted/30 rounded-lg">
                                <PriceChange value={result?.price_change_5m} label="5m" />
                                <PriceChange value={result?.price_change_1h} label="1h" />
                                <PriceChange value={result?.price_change_6h} label="6h" />
                                <PriceChange value={result?.price_change_24h} label="24h" />
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>
        );
    },
});

