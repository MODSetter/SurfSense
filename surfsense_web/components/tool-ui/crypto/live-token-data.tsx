"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, ExternalLink, Zap, RefreshCw, Activity, Droplets, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for live token data tool arguments
export const LiveTokenDataArgsSchema = z.object({
    chain: z.string(),
    token_address: z.string(),
    token_symbol: z.string().optional(),
    include_all_pairs: z.boolean().optional(),
});

export type LiveTokenDataArgs = z.infer<typeof LiveTokenDataArgsSchema>;

// Schema for live token data result (matches backend response)
export const LiveTokenDataResultSchema = z.object({
    id: z.string(),
    kind: z.literal("live_token_data"),
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
    volume_6h: z.number().optional(),
    volume_1h: z.number().optional(),
    liquidity_usd: z.number().optional(),
    market_cap: z.number().optional(),
    fdv: z.number().optional(),
    txns_24h_buys: z.number().optional(),
    txns_24h_sells: z.number().optional(),
    txns_6h_buys: z.number().optional(),
    txns_6h_sells: z.number().optional(),
    txns_1h_buys: z.number().optional(),
    txns_1h_sells: z.number().optional(),
    total_volume_24h_all_pairs: z.number().optional(),
    total_liquidity_all_pairs: z.number().optional(),
    total_buys_24h_all_pairs: z.number().optional(),
    total_sells_24h_all_pairs: z.number().optional(),
    dex: z.string().optional(),
    pair_url: z.string().optional(),
    total_pairs: z.number().optional(),
    data_source: z.string().optional(),
    error: z.string().optional(),
});

export type LiveTokenDataResult = z.infer<typeof LiveTokenDataResultSchema>;

const formatPrice = (price: string | undefined): string => {
    if (!price || price === "N/A") return "N/A";
    const num = parseFloat(price);
    if (isNaN(num)) return price;
    if (num < 0.00001) return `$${num.toExponential(2)}`;
    if (num < 1) return `$${num.toFixed(6)}`;
    return `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatLargeNumber = (num: number | undefined): string => {
    if (num === undefined || num === null || num === 0) return "N/A";
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

const formatNumber = (num: number | undefined): string => {
    if (num === undefined || num === null) return "0";
    return num.toLocaleString();
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
 * LiveTokenDataToolUI - Displays comprehensive real-time market data
 * Used when AI fetches detailed live market information
 */
export const LiveTokenDataToolUI = makeAssistantToolUI<LiveTokenDataArgs, LiveTokenDataResult>({
    toolName: "get_live_token_data",
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

        const totalTxns24h = (result?.txns_24h_buys || 0) + (result?.txns_24h_sells || 0);
        const buyRatio = totalTxns24h > 0 ? ((result?.txns_24h_buys || 0) / totalTxns24h) * 100 : 50;

        return (
            <Card className="my-3 overflow-hidden border-purple-500/20">
                <CardHeader className="pb-3 bg-gradient-to-r from-purple-500/5 to-transparent">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Activity className="h-5 w-5 text-purple-500" />
                        Live Market Data
                        {isLoading && <Badge variant="secondary" className="animate-pulse">Fetching...</Badge>}
                        {!isLoading && !hasError && (
                            <Badge variant="outline" className="text-xs text-purple-500 border-purple-500/30">
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

                            {/* Metrics Grid */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                        <BarChart3 className="h-3 w-3" /> 24h Volume
                                    </p>
                                    <p className="font-medium">{formatLargeNumber(result?.volume_24h)}</p>
                                </div>
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                        <Droplets className="h-3 w-3" /> Liquidity
                                    </p>
                                    <p className="font-medium">{formatLargeNumber(result?.liquidity_usd)}</p>
                                </div>
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground">Market Cap</p>
                                    <p className="font-medium">{formatLargeNumber(result?.market_cap)}</p>
                                </div>
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground">FDV</p>
                                    <p className="font-medium">{formatLargeNumber(result?.fdv)}</p>
                                </div>
                            </div>

                            {/* Transaction Activity */}
                            <div className="space-y-2">
                                <p className="text-sm font-medium flex items-center gap-2">
                                    <Activity className="h-4 w-4" /> 24h Transactions
                                </p>
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-green-500 transition-all"
                                            style={{ width: `${buyRatio}%` }}
                                        />
                                    </div>
                                </div>
                                <div className="flex justify-between text-sm">
                                    <span className="text-green-500">
                                        {formatNumber(result?.txns_24h_buys)} buys
                                    </span>
                                    <span className="text-muted-foreground">
                                        {formatNumber(totalTxns24h)} total
                                    </span>
                                    <span className="text-red-500">
                                        {formatNumber(result?.txns_24h_sells)} sells
                                    </span>
                                </div>
                            </div>

                            {/* DEX Info & Actions */}
                            <div className="flex items-center justify-between pt-2 border-t">
                                <div className="text-sm text-muted-foreground">
                                    <span>DEX: {result?.dex || "Unknown"}</span>
                                    {result?.total_pairs && result.total_pairs > 1 && (
                                        <span className="ml-2">• {result.total_pairs} pairs</span>
                                    )}
                                </div>
                                <Button variant="outline" size="sm" onClick={handleOpenDexScreener}>
                                    <ExternalLink className="h-4 w-4 mr-1" />
                                    DexScreener
                                </Button>
                            </div>
                        </>
                    )}
                </CardContent>
            </Card>
        );
    },
});

