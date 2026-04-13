"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Wallet, TrendingUp, TrendingDown, PieChart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";

// Schema for portfolio holding
const HoldingSchema = z.object({
    symbol: z.string(),
    name: z.string(),
    chain: z.string(),
    balance: z.number(),
    value: z.number(),
    costBasis: z.number().optional(),
    pnl: z.number().optional(),
    pnlPercent: z.number().optional(),
    allocation: z.number(),
});

// Schema for portfolio display tool arguments
export const PortfolioDisplayArgsSchema = z.object({
    holdings: z.array(HoldingSchema),
    totalValue: z.number(),
    totalPnl: z.number().optional(),
    totalPnlPercent: z.number().optional(),
    lastUpdated: z.string().optional(),
});

export type PortfolioDisplayArgs = z.infer<typeof PortfolioDisplayArgsSchema>;

// Schema for portfolio display result
export const PortfolioDisplayResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type PortfolioDisplayResult = z.infer<typeof PortfolioDisplayResultSchema>;

const formatValue = (value: number): string => {
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
    return `$${value.toFixed(2)}`;
};

/**
 * PortfolioDisplayToolUI - Displays user's portfolio inline in chat
 * Used when AI responds to "how's my portfolio?" or "show my holdings"
 */
export const PortfolioDisplayToolUI = makeAssistantToolUI<PortfolioDisplayArgs, PortfolioDisplayResult>({
    toolName: "get_portfolio",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const holdings = args.holdings || [];
        const hasPnl = args.totalPnl !== undefined;

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Wallet className="h-5 w-5 text-emerald-500" />
                            Your Portfolio
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                        {args.lastUpdated && (
                            <span className="text-xs text-muted-foreground">Updated {args.lastUpdated}</span>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Total Value */}
                    <div className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 rounded-lg p-4">
                        <p className="text-sm text-muted-foreground">Total Value</p>
                        <p className="text-3xl font-bold">{formatValue(args.totalValue)}</p>
                        {hasPnl && (
                            <p className={cn("text-sm flex items-center gap-1 mt-1", (args.totalPnl || 0) >= 0 ? "text-green-500" : "text-red-500")}>
                                {(args.totalPnl || 0) >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                                {(args.totalPnl || 0) >= 0 ? "+" : ""}{formatValue(args.totalPnl || 0)} ({(args.totalPnlPercent || 0) >= 0 ? "+" : ""}{(args.totalPnlPercent || 0).toFixed(2)}%)
                            </p>
                        )}
                    </div>

                    {/* Holdings List */}
                    {holdings.length === 0 ? (
                        <p className="text-muted-foreground text-center py-4">No holdings found</p>
                    ) : (
                        <div className="divide-y">
                            {holdings.map((holding) => (
                                <div key={holding.symbol} className="flex items-center justify-between py-3">
                                    <div className="flex items-center gap-3">
                                        <ChainIcon chain={holding.chain} size="sm" />
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium">{holding.symbol}</span>
                                                <Badge variant="secondary" className="text-xs">{holding.allocation.toFixed(1)}%</Badge>
                                            </div>
                                            <span className="text-xs text-muted-foreground">{holding.balance.toLocaleString()} tokens</span>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="font-medium">{formatValue(holding.value)}</p>
                                        {holding.pnlPercent !== undefined && (
                                            <p className={cn("text-sm", holding.pnlPercent >= 0 ? "text-green-500" : "text-red-500")}>
                                                {holding.pnlPercent >= 0 ? "+" : ""}{holding.pnlPercent.toFixed(2)}%
                                            </p>
                                        )}
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

