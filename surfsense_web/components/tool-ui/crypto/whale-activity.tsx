"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Fish, ArrowUpRight, ArrowDownRight, ExternalLink, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for whale transaction
const WhaleTransactionSchema = z.object({
    id: z.string(),
    type: z.enum(["buy", "sell", "transfer"]),
    amount: z.number(),
    amountUsd: z.number(),
    tokenSymbol: z.string(),
    walletAddress: z.string(),
    walletLabel: z.string().optional(),
    timestamp: z.string(),
    txHash: z.string().optional(),
});

// Schema for whale activity tool arguments
export const WhaleActivityArgsSchema = z.object({
    tokenSymbol: z.string(),
    chain: z.string(),
    transactions: z.array(WhaleTransactionSchema),
    summary: z.object({
        totalBuyVolume: z.number(),
        totalSellVolume: z.number(),
        netFlow: z.number(),
        uniqueWhales: z.number(),
    }).optional(),
});

export type WhaleActivityArgs = z.infer<typeof WhaleActivityArgsSchema>;

// Schema for whale activity result
export const WhaleActivityResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type WhaleActivityResult = z.infer<typeof WhaleActivityResultSchema>;

const formatLargeNumber = (num: number): string => {
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    return `$${num.toFixed(2)}`;
};

const shortenAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

const formatTimeAgo = (timestamp: string): string => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
};

/**
 * WhaleActivityToolUI - Displays whale transactions inline in chat
 * Used when AI responds to "show whale activity for BULLA" or similar
 */
export const WhaleActivityToolUI = makeAssistantToolUI<WhaleActivityArgs, WhaleActivityResult>({
    toolName: "get_whale_activity",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const transactions = args.transactions || [];
        const summary = args.summary;

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Fish className="h-5 w-5 text-blue-500" />
                            Whale Activity - {args.tokenSymbol}
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                        <ChainIcon chain={args.chain} size="sm" />
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Summary Stats */}
                    {summary && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div className="bg-green-500/10 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Buy Volume</p>
                                <p className="font-medium text-green-500">{formatLargeNumber(summary.totalBuyVolume)}</p>
                            </div>
                            <div className="bg-red-500/10 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Sell Volume</p>
                                <p className="font-medium text-red-500">{formatLargeNumber(summary.totalSellVolume)}</p>
                            </div>
                            <div className={cn("rounded-lg p-3", summary.netFlow >= 0 ? "bg-green-500/10" : "bg-red-500/10")}>
                                <p className="text-xs text-muted-foreground">Net Flow</p>
                                <p className={cn("font-medium", summary.netFlow >= 0 ? "text-green-500" : "text-red-500")}>
                                    {summary.netFlow >= 0 ? "+" : ""}{formatLargeNumber(summary.netFlow)}
                                </p>
                            </div>
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Unique Whales</p>
                                <p className="font-medium">{summary.uniqueWhales}</p>
                            </div>
                        </div>
                    )}

                    {/* Transaction List */}
                    {transactions.length === 0 ? (
                        <p className="text-muted-foreground text-center py-4">No whale transactions detected</p>
                    ) : (
                        <div className="divide-y max-h-[300px] overflow-y-auto">
                            {transactions.map((tx) => (
                                <div key={tx.id} className="flex items-center justify-between py-3">
                                    <div className="flex items-center gap-3">
                                        <div className={cn("p-2 rounded-full", tx.type === "buy" ? "bg-green-500/10" : tx.type === "sell" ? "bg-red-500/10" : "bg-muted")}>
                                            {tx.type === "buy" ? <ArrowUpRight className="h-4 w-4 text-green-500" /> : tx.type === "sell" ? <ArrowDownRight className="h-4 w-4 text-red-500" /> : <ArrowUpRight className="h-4 w-4" />}
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className={cn("font-medium capitalize", tx.type === "buy" ? "text-green-500" : tx.type === "sell" ? "text-red-500" : "")}>
                                                    {tx.type}
                                                </span>
                                                <span className="font-medium">{formatLargeNumber(tx.amountUsd)}</span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <span>{tx.walletLabel || shortenAddress(tx.walletAddress)}</span>
                                                <Clock className="h-3 w-3" />
                                                <span>{formatTimeAgo(tx.timestamp)}</span>
                                            </div>
                                        </div>
                                    </div>
                                    {tx.txHash && (
                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                            <ExternalLink className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    },
});

