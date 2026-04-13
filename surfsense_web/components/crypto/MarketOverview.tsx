"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenPrice } from "@/lib/mock/cryptoMockData";
import { formatPrice, formatPercent, formatLargeNumber } from "@/lib/mock/cryptoMockData";

interface MarketOverviewProps {
    tokens: TokenPrice[];
    className?: string;
}

function MarketCard({ token }: { token: TokenPrice }) {
    const isPositive = token.priceChange24h > 0;
    const isNegative = token.priceChange24h < 0;

    return (
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
            <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-lg font-bold">
                    {token.icon || token.symbol.charAt(0)}
                </div>
                <div>
                    <div className="font-semibold">{token.symbol}</div>
                    <div className="text-xs text-muted-foreground">{token.name}</div>
                </div>
            </div>
            <div className="text-right">
                <div className="font-semibold">{formatPrice(token.price)}</div>
                <div
                    className={cn(
                        "flex items-center justify-end gap-1 text-xs",
                        isPositive && "text-green-500",
                        isNegative && "text-red-500",
                        !isPositive && !isNegative && "text-muted-foreground"
                    )}
                >
                    {isPositive && <TrendingUp className="h-3 w-3" />}
                    {isNegative && <TrendingDown className="h-3 w-3" />}
                    {formatPercent(token.priceChange24h)}
                </div>
            </div>
        </div>
    );
}

export function MarketOverview({ tokens, className }: MarketOverviewProps) {
    return (
        <Card className={cn("", className)}>
            <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                    <span>📊</span> Market Overview
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                {tokens.map((token) => (
                    <MarketCard key={token.symbol} token={token} />
                ))}
            </CardContent>
        </Card>
    );
}

