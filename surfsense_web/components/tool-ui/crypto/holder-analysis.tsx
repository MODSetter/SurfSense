"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Users, AlertTriangle, Shield, Crown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for holder
const HolderSchema = z.object({
    rank: z.number(),
    address: z.string(),
    label: z.string().optional(),
    balance: z.number(),
    percentage: z.number(),
    isContract: z.boolean().optional(),
});

// Schema for holder analysis tool arguments
export const HolderAnalysisArgsSchema = z.object({
    tokenSymbol: z.string(),
    chain: z.string(),
    totalHolders: z.number(),
    top10Percentage: z.number(),
    top50Percentage: z.number().optional(),
    holders: z.array(HolderSchema),
    concentrationRisk: z.enum(["low", "medium", "high", "critical"]).optional(),
});

export type HolderAnalysisArgs = z.infer<typeof HolderAnalysisArgsSchema>;

// Schema for holder analysis result
export const HolderAnalysisResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type HolderAnalysisResult = z.infer<typeof HolderAnalysisResultSchema>;

const shortenAddress = (address: string): string => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

const formatBalance = (balance: number): string => {
    if (balance >= 1e9) return `${(balance / 1e9).toFixed(2)}B`;
    if (balance >= 1e6) return `${(balance / 1e6).toFixed(2)}M`;
    if (balance >= 1e3) return `${(balance / 1e3).toFixed(2)}K`;
    return balance.toFixed(2);
};

const getRiskColor = (risk: string) => {
    switch (risk) {
        case "low": return "text-green-500 bg-green-500/10";
        case "medium": return "text-yellow-500 bg-yellow-500/10";
        case "high": return "text-orange-500 bg-orange-500/10";
        case "critical": return "text-red-500 bg-red-500/10";
        default: return "text-muted-foreground bg-muted";
    }
};

/**
 * HolderAnalysisToolUI - Displays holder distribution inline in chat
 * Used when AI responds to "who holds BULLA?" or "analyze holders"
 */
export const HolderAnalysisToolUI = makeAssistantToolUI<HolderAnalysisArgs, HolderAnalysisResult>({
    toolName: "analyze_holders",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const holders = args.holders || [];
        const risk = args.concentrationRisk || "medium";

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Users className="h-5 w-5 text-purple-500" />
                            Holder Analysis - {args.tokenSymbol}
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                        <ChainIcon chain={args.chain} size="sm" />
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Summary Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="bg-muted/50 rounded-lg p-3">
                            <p className="text-xs text-muted-foreground">Total Holders</p>
                            <p className="font-medium">{args.totalHolders.toLocaleString()}</p>
                        </div>
                        <div className={cn("rounded-lg p-3", args.top10Percentage > 50 ? "bg-red-500/10" : "bg-muted/50")}>
                            <p className="text-xs text-muted-foreground">Top 10 Hold</p>
                            <p className={cn("font-medium", args.top10Percentage > 50 && "text-red-500")}>{args.top10Percentage.toFixed(1)}%</p>
                        </div>
                        {args.top50Percentage && (
                            <div className="bg-muted/50 rounded-lg p-3">
                                <p className="text-xs text-muted-foreground">Top 50 Hold</p>
                                <p className="font-medium">{args.top50Percentage.toFixed(1)}%</p>
                            </div>
                        )}
                        <div className={cn("rounded-lg p-3", getRiskColor(risk))}>
                            <p className="text-xs text-muted-foreground">Concentration Risk</p>
                            <p className="font-medium capitalize">{risk}</p>
                        </div>
                    </div>

                    {/* Risk Warning */}
                    {(risk === "high" || risk === "critical") && (
                        <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 text-sm bg-yellow-500/10 rounded-lg p-3">
                            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                            <span>High holder concentration detected. Top wallets could significantly impact price.</span>
                        </div>
                    )}

                    {/* Top Holders List */}
                    <div className="space-y-2">
                        <p className="text-sm font-medium text-muted-foreground">Top Holders</p>
                        <div className="divide-y max-h-[250px] overflow-y-auto">
                            {holders.slice(0, 10).map((holder) => (
                                <div key={holder.address} className="flex items-center justify-between py-2">
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm font-bold text-muted-foreground w-6">#{holder.rank}</span>
                                        {holder.rank <= 3 && <Crown className={cn("h-4 w-4", holder.rank === 1 ? "text-yellow-500" : holder.rank === 2 ? "text-gray-400" : "text-amber-600")} />}
                                        <div>
                                            <p className="font-medium text-sm">{holder.label || shortenAddress(holder.address)}</p>
                                            {holder.isContract && <Badge variant="outline" className="text-xs">Contract</Badge>}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="font-medium text-sm">{holder.percentage.toFixed(2)}%</p>
                                        <p className="text-xs text-muted-foreground">{formatBalance(holder.balance)}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    },
});

