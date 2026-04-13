"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Wallet, PieChart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChainIcon } from "./ChainIcon";
import type { PortfolioSummary as PortfolioSummaryType, PortfolioToken } from "@/lib/mock/cryptoMockData";
import { formatPrice, formatPercent, formatLargeNumber } from "@/lib/mock/cryptoMockData";

interface PortfolioSummaryProps {
    portfolio: PortfolioSummaryType;
    className?: string;
}

function StatCard({
    label,
    value,
    change,
    changePercent,
}: {
    label: string;
    value: string;
    change?: number;
    changePercent?: number;
}) {
    const isPositive = change !== undefined && change > 0;
    const isNegative = change !== undefined && change < 0;

    return (
        <div className="p-4 rounded-lg bg-muted/50">
            <p className="text-sm text-muted-foreground mb-1">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
            {change !== undefined && changePercent !== undefined && (
                <div
                    className={cn(
                        "flex items-center gap-1 text-sm mt-1",
                        isPositive && "text-green-500",
                        isNegative && "text-red-500",
                        !isPositive && !isNegative && "text-muted-foreground"
                    )}
                >
                    {isPositive && <TrendingUp className="h-3 w-3" />}
                    {isNegative && <TrendingDown className="h-3 w-3" />}
                    <span>{formatPrice(Math.abs(change))}</span>
                    <span>({formatPercent(changePercent)})</span>
                </div>
            )}
        </div>
    );
}

function TokenRow({ token }: { token: PortfolioToken }) {
    const isPositive = token.pnl > 0;
    const isNegative = token.pnl < 0;

    return (
        <div className="flex items-center justify-between py-2 border-b last:border-0">
            <div className="flex items-center gap-3">
                <ChainIcon chain={token.chain} size="sm" />
                <div>
                    <div className="font-medium">{token.symbol}</div>
                    <div className="text-xs text-muted-foreground">
                        {token.amount.toLocaleString()} tokens
                    </div>
                </div>
            </div>
            <div className="text-right">
                <div className="font-medium">{formatPrice(token.value)}</div>
                <div
                    className={cn(
                        "text-xs",
                        isPositive && "text-green-500",
                        isNegative && "text-red-500"
                    )}
                >
                    {formatPercent(token.pnlPercent)}
                </div>
            </div>
            <div className="w-16 text-right">
                <div className="text-sm text-muted-foreground">{token.allocation.toFixed(1)}%</div>
                <div className="h-1.5 w-full bg-muted rounded-full mt-1 overflow-hidden">
                    <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${token.allocation}%` }}
                    />
                </div>
            </div>
        </div>
    );
}

export function PortfolioSummary({ portfolio, className }: PortfolioSummaryProps) {
    return (
        <Card className={cn("", className)}>
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <Wallet className="h-5 w-5" /> Portfolio
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Summary Stats */}
                <div className="grid grid-cols-2 gap-3">
                    <StatCard
                        label="Total Value"
                        value={formatPrice(portfolio.totalValue)}
                        change={portfolio.change24h}
                        changePercent={portfolio.change24hPercent}
                    />
                    <StatCard
                        label="Total P&L"
                        value={formatPrice(portfolio.totalPnl)}
                        change={portfolio.totalPnl}
                        changePercent={portfolio.totalPnlPercent}
                    />
                </div>

                {/* Token Holdings */}
                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <PieChart className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Holdings</span>
                    </div>
                    <div className="space-y-1">
                        {portfolio.tokens.map((token) => (
                            <TokenRow key={token.id} token={token} />
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

