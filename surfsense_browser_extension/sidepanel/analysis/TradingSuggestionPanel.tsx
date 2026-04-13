import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    TrendingUp,
    TrendingDown,
    Target,
    AlertCircle,
    Info,
    DollarSign,
    Percent,
    Clock,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface TradingSuggestion {
    tokenAddress: string;
    tokenSymbol: string;
    tokenName: string;
    chain: string;
    currentPrice: number;
    timestamp: Date;
    
    entry: {
        min: number;
        max: number;
        reasoning: string;
    };
    
    targets: {
        level: number;
        price: number;
        percentGain: number;
        confidence: number;
    }[];
    
    stopLoss: {
        price: number;
        percentLoss: number;
        reasoning: string;
    };
    
    riskReward: number;
    overallConfidence: number;
    
    technicalLevels: {
        support: number[];
        resistance: number[];
    };
    
    reasoning: string[];
    invalidationConditions: string[];
}

export interface TradingSuggestionPanelProps {
    /** Trading suggestion data */
    suggestion: TradingSuggestion;
    /** Callback when "Set Alerts" is clicked */
    onSetAlerts?: () => void;
    /** Callback when "View Chart" is clicked */
    onViewChart?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * TradingSuggestionPanel - AI-powered entry/exit suggestions
 *
 * Features:
 * - Entry zone recommendations
 * - Multiple take-profit targets
 * - Stop-loss suggestions
 * - Risk/reward ratio calculation
 * - Technical analysis levels
 * - AI reasoning and invalidation conditions
 */
export function TradingSuggestionPanel({
    suggestion,
    onSetAlerts,
    onViewChart,
    className,
}: TradingSuggestionPanelProps) {
    const [showDetails, setShowDetails] = useState(false);

    const formatPrice = (price: number) => {
        if (price < 0.01) return `$${price.toFixed(8)}`;
        if (price < 1) return `$${price.toFixed(6)}`;
        return `$${price.toFixed(4)}`;
    };

    const getRiskRewardColor = (ratio: number) => {
        if (ratio >= 3) return "text-green-600 dark:text-green-400";
        if (ratio >= 2) return "text-yellow-600 dark:text-yellow-400";
        return "text-red-600 dark:text-red-400";
    };

    const getRiskRewardLabel = (ratio: number) => {
        if (ratio >= 3) return "Excellent";
        if (ratio >= 2) return "Good";
        if (ratio >= 1.5) return "Fair";
        return "Poor";
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <Target className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">Trading Suggestion</h2>
                        <p className="text-xs text-muted-foreground">
                            {suggestion.tokenSymbol} • <ChainIcon chain={suggestion.chain} size="xs" className="inline" />
                        </p>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-xs text-muted-foreground">Confidence</div>
                    <div className="font-bold text-sm">{suggestion.overallConfidence}%</div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Current Price */}
                <div className="p-3 bg-muted/50 rounded-lg">
                    <div className="text-xs text-muted-foreground mb-1">Current Price</div>
                    <div className="font-bold text-2xl">{formatPrice(suggestion.currentPrice)}</div>
                </div>

                {/* Entry Zone */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <h3 className="font-semibold text-sm">Entry Zone</h3>
                    </div>
                    <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                            <span className="font-bold text-lg text-green-600 dark:text-green-400">
                                {formatPrice(suggestion.entry.min)} - {formatPrice(suggestion.entry.max)}
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground">{suggestion.entry.reasoning}</p>
                    </div>
                </div>

                {/* Targets */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Target className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Take Profit Targets</h3>
                    </div>
                    <div className="space-y-2">
                        {suggestion.targets.map((target) => (
                            <div
                                key={target.level}
                                className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg"
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-semibold text-sm">🎯 Target {target.level}</span>
                                    <span className="text-xs text-muted-foreground">
                                        Confidence: {target.confidence}%
                                    </span>
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="font-bold text-blue-600 dark:text-blue-400">
                                        {formatPrice(target.price)}
                                    </span>
                                    <span className="font-semibold text-sm text-green-600 dark:text-green-400">
                                        +{target.percentGain.toFixed(1)}%
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Stop Loss */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <h3 className="font-semibold text-sm">Stop Loss</h3>
                    </div>
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                            <span className="font-bold text-lg text-red-600 dark:text-red-400">
                                {formatPrice(suggestion.stopLoss.price)}
                            </span>
                            <span className="font-semibold text-sm text-red-600 dark:text-red-400">
                                {suggestion.stopLoss.percentLoss.toFixed(1)}%
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground">{suggestion.stopLoss.reasoning}</p>
                    </div>
                </div>

                {/* Risk/Reward */}
                <div className="p-4 bg-muted/50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Risk/Reward Ratio</span>
                        <span className={cn("font-bold text-lg", getRiskRewardColor(suggestion.riskReward))}>
                            1:{suggestion.riskReward.toFixed(1)}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className={cn(
                            "px-2 py-1 rounded text-xs font-medium",
                            suggestion.riskReward >= 3 ? "bg-green-500/20 text-green-600 dark:text-green-400" :
                            suggestion.riskReward >= 2 ? "bg-yellow-500/20 text-yellow-600 dark:text-yellow-400" :
                            "bg-red-500/20 text-red-600 dark:text-red-400"
                        )}>
                            {getRiskRewardLabel(suggestion.riskReward)}
                        </div>
                    </div>
                </div>

                {/* Why? Section */}
                <div className="space-y-2">
                    <button
                        className="flex items-center gap-2 w-full"
                        onClick={() => setShowDetails(!showDetails)}
                    >
                        <Info className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Why?</h3>
                        <div className={cn(
                            "ml-auto transition-transform",
                            showDetails && "rotate-180"
                        )}>
                            ▼
                        </div>
                    </button>
                    
                    {showDetails && (
                        <div className="space-y-3 pl-6">
                            <div>
                                <h4 className="text-xs font-semibold text-muted-foreground mb-1">Reasoning:</h4>
                                <ul className="space-y-1">
                                    {suggestion.reasoning.map((reason, i) => (
                                        <li key={i} className="text-xs flex items-start gap-2">
                                            <span className="text-green-600 dark:text-green-400">•</span>
                                            <span>{reason}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            
                            <div>
                                <h4 className="text-xs font-semibold text-muted-foreground mb-1">Invalidation Conditions:</h4>
                                <ul className="space-y-1">
                                    {suggestion.invalidationConditions.map((condition, i) => (
                                        <li key={i} className="text-xs flex items-start gap-2">
                                            <AlertCircle className="h-3 w-3 text-red-600 dark:text-red-400 mt-0.5" />
                                            <span>{condition}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer Actions */}
            <div className="border-t p-3 space-y-2">
                <Button
                    variant="default"
                    className="w-full"
                    onClick={onSetAlerts}
                >
                    Set Alerts for These Levels
                </Button>
                <Button
                    variant="outline"
                    className="w-full"
                    onClick={onViewChart}
                >
                    View Chart
                </Button>
            </div>
        </div>
    );
}
