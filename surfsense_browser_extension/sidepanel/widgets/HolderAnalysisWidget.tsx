import { cn } from "~/lib/utils";
import { Users, AlertTriangle, Crown } from "lucide-react";
import { ChainIcon } from "../components/shared/ChainIcon";

export interface Holder {
    rank: number;
    address: string;
    label?: string;
    balance: number;
    percentage: number;
    isContract?: boolean;
}

export interface HolderAnalysisData {
    tokenSymbol: string;
    chain: string;
    totalHolders: number;
    top10Percentage: number;
    top50Percentage?: number;
    holders: Holder[];
    concentrationRisk?: "low" | "medium" | "high" | "critical";
}

export interface HolderAnalysisWidgetProps {
    /** Holder analysis data */
    data: HolderAnalysisData;
    /** Callback when holder is clicked */
    onHolderClick?: (holder: Holder) => void;
    /** Additional class names */
    className?: string;
}

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
 * HolderAnalysisWidget - Displays holder distribution inline in chat
 * Used when AI responds to "who holds BULLA?" or "analyze holders"
 */
export function HolderAnalysisWidget({
    data,
    onHolderClick,
    className,
}: HolderAnalysisWidgetProps) {
    const risk = data.concentrationRisk || "medium";

    return (
        <div className={cn("rounded-lg border bg-card p-4 my-2", className)}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Users className="h-5 w-5 text-purple-500" />
                    <span className="font-medium text-sm">Holder Analysis - {data.tokenSymbol}</span>
                </div>
                <ChainIcon chain={data.chain} size="sm" />
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="bg-muted/50 rounded p-2">
                    <p className="text-xs text-muted-foreground">Total Holders</p>
                    <p className="font-medium text-sm">{data.totalHolders.toLocaleString()}</p>
                </div>
                <div className={cn("rounded p-2", data.top10Percentage > 50 ? "bg-red-500/10" : "bg-muted/50")}>
                    <p className="text-xs text-muted-foreground">Top 10 Hold</p>
                    <p className={cn("font-medium text-sm", data.top10Percentage > 50 && "text-red-500")}>
                        {data.top10Percentage.toFixed(1)}%
                    </p>
                </div>
                {data.top50Percentage && (
                    <div className="bg-muted/50 rounded p-2">
                        <p className="text-xs text-muted-foreground">Top 50 Hold</p>
                        <p className="font-medium text-sm">{data.top50Percentage.toFixed(1)}%</p>
                    </div>
                )}
                <div className={cn("rounded p-2", getRiskColor(risk))}>
                    <p className="text-xs text-muted-foreground">Concentration Risk</p>
                    <p className="font-medium text-sm capitalize">{risk}</p>
                </div>
            </div>

            {/* Risk Warning */}
            {(risk === "high" || risk === "critical") && (
                <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 text-xs bg-yellow-500/10 rounded-lg p-2 mb-3">
                    <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                    <span>High holder concentration. Top wallets could impact price.</span>
                </div>
            )}

            {/* Top Holders List */}
            <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground mb-2">Top Holders</p>
                <div className="divide-y max-h-[200px] overflow-y-auto">
                    {data.holders.slice(0, 10).map((holder) => (
                        <div
                            key={holder.address}
                            className="flex items-center justify-between py-2 hover:bg-muted/50 -mx-2 px-2 rounded cursor-pointer transition-colors"
                            onClick={() => onHolderClick?.(holder)}
                        >
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-muted-foreground w-5">#{holder.rank}</span>
                                {holder.rank <= 3 && (
                                    <Crown className={cn(
                                        "h-3.5 w-3.5",
                                        holder.rank === 1 ? "text-yellow-500" :
                                        holder.rank === 2 ? "text-gray-400" : "text-amber-600"
                                    )} />
                                )}
                                <div>
                                    <p className="font-medium text-xs">{holder.label || shortenAddress(holder.address)}</p>
                                    {holder.isContract && (
                                        <span className="text-[10px] bg-muted px-1 rounded">Contract</span>
                                    )}
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="font-medium text-xs">{holder.percentage.toFixed(2)}%</p>
                                <p className="text-[10px] text-muted-foreground">{formatBalance(holder.balance)}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

