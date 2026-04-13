import { cn } from "~/lib/utils";
import { 
    Shield, 
    CheckCircle, 
    AlertTriangle, 
    XCircle,
    ExternalLink,
    Clock,
    Star,
    Bell
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { RiskBadge, getRiskLevelFromScore, type RiskLevel } from "../components/shared";

export interface SafetyFactor {
    /** Category name (e.g., "Liquidity", "Contract", "Holders") */
    category: string;
    /** Status of this factor */
    status: "positive" | "warning" | "danger";
    /** Description of the finding */
    description: string;
}

export interface SafetyScoreProps {
    /** Safety score from 0-100 */
    score: number;
    /** Risk level (can be auto-calculated from score) */
    level?: RiskLevel;
    /** Individual safety factors */
    factors: SafetyFactor[];
    /** Data sources used for analysis */
    sources?: string[];
    /** When the analysis was performed */
    timestamp?: Date;
    /** Token symbol for display */
    tokenSymbol?: string;
    /** Callback when "Add to Watchlist" is clicked */
    onAddToWatchlist?: () => void;
    /** Callback when "Set Alert" is clicked */
    onSetAlert?: () => void;
    /** Whether token is already in watchlist */
    isInWatchlist?: boolean;
    /** Additional class names */
    className?: string;
}

const STATUS_CONFIG = {
    positive: {
        icon: CheckCircle,
        color: "text-green-600 dark:text-green-400",
        bgColor: "bg-green-500/10",
    },
    warning: {
        icon: AlertTriangle,
        color: "text-yellow-600 dark:text-yellow-400",
        bgColor: "bg-yellow-500/10",
    },
    danger: {
        icon: XCircle,
        color: "text-red-600 dark:text-red-400",
        bgColor: "bg-red-500/10",
    },
};

/**
 * SafetyScoreDisplay - Comprehensive safety analysis visualization
 * 
 * Features:
 * - Visual score indicator (0-100)
 * - Risk level badge
 * - Categorized safety factors with status icons
 * - Data sources attribution
 * - Quick actions (Add to Watchlist, Set Alert)
 */
export function SafetyScoreDisplay({
    score,
    level,
    factors,
    sources = [],
    timestamp,
    tokenSymbol,
    onAddToWatchlist,
    onSetAlert,
    isInWatchlist = false,
    className,
}: SafetyScoreProps) {
    const riskLevel = level || getRiskLevelFromScore(score);
    
    // Group factors by status
    const positiveFactors = factors.filter(f => f.status === "positive");
    const warningFactors = factors.filter(f => f.status === "warning");
    const dangerFactors = factors.filter(f => f.status === "danger");

    // Calculate score color
    const getScoreColor = () => {
        if (score >= 80) return "text-green-500";
        if (score >= 60) return "text-green-400";
        if (score >= 40) return "text-yellow-500";
        if (score >= 20) return "text-orange-500";
        return "text-red-500";
    };

    // Calculate progress bar color
    const getProgressColor = () => {
        if (score >= 80) return "bg-green-500";
        if (score >= 60) return "bg-green-400";
        if (score >= 40) return "bg-yellow-500";
        if (score >= 20) return "bg-orange-500";
        return "bg-red-500";
    };

    return (
        <div className={cn("rounded-lg border bg-card p-4", className)}>
            {/* Header with score */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                        <Shield className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-lg">
                            Safety Analysis
                            {tokenSymbol && <span className="text-muted-foreground ml-1">({tokenSymbol})</span>}
                        </h3>
                        <RiskBadge level={riskLevel} score={score} showScore size="sm" />
                    </div>
                </div>
                
                {/* Large score display */}
                <div className="text-right">
                    <div className={cn("text-3xl font-bold", getScoreColor())}>
                        {score}
                    </div>
                    <div className="text-xs text-muted-foreground">/ 100</div>
                </div>
            </div>

            {/* Score progress bar */}
            <div className="h-2 bg-muted rounded-full overflow-hidden mb-4">
                <div 
                    className={cn("h-full transition-all duration-500", getProgressColor())}
                    style={{ width: `${score}%` }}
                />
            </div>

            {/* Safety factors */}
            <div className="space-y-3 mb-4">
                {/* Danger factors first */}
                {dangerFactors.length > 0 && (
                    <FactorSection title="🚨 Red Flags" factors={dangerFactors} status="danger" />
                )}

                {/* Warning factors */}
                {warningFactors.length > 0 && (
                    <FactorSection title="⚠️ Warnings" factors={warningFactors} status="warning" />
                )}

                {/* Positive factors */}
                {positiveFactors.length > 0 && (
                    <FactorSection title="✅ Positive Signals" factors={positiveFactors} status="positive" />
                )}
            </div>

            {/* Action buttons */}
            <div className="flex gap-2 mb-4">
                <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={onAddToWatchlist}
                >
                    <Star className={cn("mr-1 h-4 w-4", isInWatchlist && "fill-yellow-500 text-yellow-500")} />
                    {isInWatchlist ? "In Watchlist" : "Add to Watchlist"}
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={onSetAlert}
                >
                    <Bell className="mr-1 h-4 w-4" />
                    Set Alert
                </Button>
            </div>

            {/* Footer with sources and timestamp */}
            <div className="pt-3 border-t text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>
                            {timestamp
                                ? `Analyzed ${timestamp.toLocaleTimeString()}`
                                : "Just now"
                            }
                        </span>
                    </div>
                    {sources.length > 0 && (
                        <div className="flex items-center gap-1">
                            <ExternalLink className="h-3 w-3" />
                            <span>{sources.length} sources</span>
                        </div>
                    )}
                </div>
                {sources.length > 0 && (
                    <div className="mt-1 text-xs opacity-70">
                        Sources: {sources.join(", ")}
                    </div>
                )}
            </div>
        </div>
    );
}

/**
 * FactorSection - Grouped display of safety factors
 */
function FactorSection({
    title,
    factors,
    status
}: {
    title: string;
    factors: SafetyFactor[];
    status: "positive" | "warning" | "danger";
}) {
    const config = STATUS_CONFIG[status];
    const Icon = config.icon;

    return (
        <div>
            <h4 className="text-sm font-medium mb-2">{title}</h4>
            <div className="space-y-1.5">
                {factors.map((factor, index) => (
                    <div
                        key={index}
                        className={cn(
                            "flex items-start gap-2 p-2 rounded-md text-sm",
                            config.bgColor
                        )}
                    >
                        <Icon className={cn("h-4 w-4 mt-0.5 flex-shrink-0", config.color)} />
                        <div>
                            <span className="font-medium">{factor.category}:</span>{" "}
                            <span className="text-muted-foreground">{factor.description}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Export types for use in other components
export type { SafetyFactor };

