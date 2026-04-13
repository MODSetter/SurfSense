"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Target, AlertCircle, Info, TrendingUp, TrendingDown, Bell, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainIcon } from "@/components/crypto/ChainIcon";
import { useState } from "react";

// Schema for trading suggestion tool arguments
export const TradingSuggestionArgsSchema = z.object({
    tokenSymbol: z.string(),
    tokenName: z.string().optional(),
    chain: z.string(),
    contractAddress: z.string().optional(),
    currentPrice: z.number(),
    entry: z.object({
        min: z.number(),
        max: z.number(),
        reasoning: z.string(),
    }),
    targets: z.array(z.object({
        level: z.number(),
        price: z.number(),
        percentGain: z.number(),
        confidence: z.number(),
    })),
    stopLoss: z.object({
        price: z.number(),
        percentLoss: z.number(),
        reasoning: z.string(),
    }),
    riskReward: z.number(),
    overallConfidence: z.number(),
    reasoning: z.array(z.string()),
    invalidationConditions: z.array(z.string()),
});

export type TradingSuggestionArgs = z.infer<typeof TradingSuggestionArgsSchema>;

// Schema for trading suggestion result
export const TradingSuggestionResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
    alertsSet: z.boolean().optional(),
});

export type TradingSuggestionResult = z.infer<typeof TradingSuggestionResultSchema>;

const formatPrice = (price: number): string => {
    if (price < 0.00001) return `$${price.toExponential(2)}`;
    if (price < 0.01) return `$${price.toFixed(8)}`;
    if (price < 1) return `$${price.toFixed(6)}`;
    return `$${price.toFixed(4)}`;
};

const getRiskRewardColor = (ratio: number) => {
    if (ratio >= 3) return "text-green-500";
    if (ratio >= 2) return "text-yellow-500";
    return "text-red-500";
};

const getRiskRewardLabel = (ratio: number) => {
    if (ratio >= 3) return "Excellent";
    if (ratio >= 2) return "Good";
    if (ratio >= 1.5) return "Fair";
    return "Poor";
};

/**
 * TradingSuggestionToolUI - Displays AI-powered trading suggestions in chat
 * Used when AI responds to queries like "suggest entry for BONK" or "trading suggestion for SOL"
 */
export const TradingSuggestionToolUI = makeAssistantToolUI<TradingSuggestionArgs, TradingSuggestionResult>({
    toolName: "trading_suggestion",
    render: ({ args, result, status }) => {
        const [showDetails, setShowDetails] = useState(false);
        const isLoading = status.type === "running";

        const handleOpenDexScreener = () => {
            if (args.contractAddress) {
                window.open(`https://dexscreener.com/${args.chain}/${args.contractAddress}`, "_blank");
            }
        };

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Target className="h-5 w-5 text-primary" />
                            Trading Suggestion
                            {isLoading && <Badge variant="secondary" className="animate-pulse">Analyzing...</Badge>}
                        </div>
                        <div className="text-right">
                            <div className="text-xs text-muted-foreground">Confidence</div>
                            <div className="font-bold text-sm">{args.overallConfidence}%</div>
                        </div>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Token Header */}
                    <div className="flex items-center gap-3">
                        <ChainIcon chain={args.chain} size="md" />
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="font-bold text-lg">{args.tokenSymbol}</span>
                                {args.tokenName && <span className="text-muted-foreground text-sm">{args.tokenName}</span>}
                            </div>
                            <span className="font-medium text-xl">{formatPrice(args.currentPrice)}</span>
                        </div>
                    </div>

                    {/* Entry Zone */}
                    <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 rounded-full bg-green-500" />
                            <span className="font-semibold text-sm">Entry Zone</span>
                        </div>
                        <div className="font-bold text-lg text-green-600 dark:text-green-400 mb-1">
                            {formatPrice(args.entry.min)} - {formatPrice(args.entry.max)}
                        </div>
                        <p className="text-xs text-muted-foreground">{args.entry.reasoning}</p>
                    </div>

                    {/* Targets */}
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <Target className="h-4 w-4 text-muted-foreground" />
                            <span className="font-semibold text-sm">Take Profit Targets</span>
                        </div>
                        <div className="grid gap-2">
                            {args.targets.map((target) => (
                                <div key={target.level} className="p-2 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm">🎯 T{target.level}</span>
                                        <span className="font-bold text-blue-600 dark:text-blue-400">{formatPrice(target.price)}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-green-500 font-medium">+{target.percentGain.toFixed(1)}%</span>
                                        <Badge variant="outline" className="text-xs">{target.confidence}%</Badge>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Stop Loss */}
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 rounded-full bg-red-500" />
                            <span className="font-semibold text-sm">Stop Loss</span>
                        </div>
                        <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-lg text-red-600 dark:text-red-400">
                                {formatPrice(args.stopLoss.price)}
                            </span>
                            <span className="text-sm text-red-500 font-medium">
                                {args.stopLoss.percentLoss.toFixed(1)}%
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground">{args.stopLoss.reasoning}</p>
                    </div>

                    {/* Risk/Reward */}
                    <div className="p-3 bg-muted/50 rounded-lg flex items-center justify-between">
                        <span className="text-sm font-medium">Risk/Reward Ratio</span>
                        <div className="flex items-center gap-2">
                            <Badge variant={args.riskReward >= 3 ? "default" : args.riskReward >= 2 ? "secondary" : "destructive"}>
                                {getRiskRewardLabel(args.riskReward)}
                            </Badge>
                            <span className={cn("font-bold text-lg", getRiskRewardColor(args.riskReward))}>
                                1:{args.riskReward.toFixed(1)}
                            </span>
                        </div>
                    </div>

                    {/* Why? Section - Collapsible */}
                    <div className="space-y-2">
                        <button
                            className="flex items-center gap-2 w-full text-left"
                            onClick={() => setShowDetails(!showDetails)}
                        >
                            <Info className="h-4 w-4 text-muted-foreground" />
                            <span className="font-semibold text-sm">Why?</span>
                            <span className={cn("ml-auto transition-transform text-xs", showDetails && "rotate-180")}>▼</span>
                        </button>

                        {showDetails && (
                            <div className="space-y-3 pl-6 text-sm">
                                <div>
                                    <h4 className="text-xs font-semibold text-muted-foreground mb-1">Reasoning:</h4>
                                    <ul className="space-y-1">
                                        {args.reasoning.map((reason, i) => (
                                            <li key={i} className="text-xs flex items-start gap-2">
                                                <TrendingUp className="h-3 w-3 text-green-500 mt-0.5 flex-shrink-0" />
                                                <span>{reason}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                <div>
                                    <h4 className="text-xs font-semibold text-muted-foreground mb-1">Invalidation:</h4>
                                    <ul className="space-y-1">
                                        {args.invalidationConditions.map((condition, i) => (
                                            <li key={i} className="text-xs flex items-start gap-2">
                                                <AlertCircle className="h-3 w-3 text-red-500 mt-0.5 flex-shrink-0" />
                                                <span>{condition}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-2">
                        <Button variant="default" size="sm" className="flex-1">
                            <Bell className="h-4 w-4 mr-2" />
                            Set Alerts
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

