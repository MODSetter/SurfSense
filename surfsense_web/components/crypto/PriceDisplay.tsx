"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { formatPrice, formatPercent } from "@/lib/mock/cryptoMockData";

interface PriceDisplayProps {
    price: number;
    priceChange?: number;
    size?: "sm" | "md" | "lg";
    showIcon?: boolean;
    className?: string;
}

const sizeClasses = {
    sm: { price: "text-sm font-medium", change: "text-xs" },
    md: { price: "text-lg font-semibold", change: "text-sm" },
    lg: { price: "text-2xl font-bold", change: "text-base" },
};

export function PriceDisplay({
    price,
    priceChange,
    size = "md",
    showIcon = true,
    className,
}: PriceDisplayProps) {
    const isPositive = priceChange !== undefined && priceChange > 0;
    const isNegative = priceChange !== undefined && priceChange < 0;
    const isNeutral = priceChange === undefined || priceChange === 0;

    return (
        <div className={cn("flex items-baseline gap-2", className)}>
            <span className={sizeClasses[size].price}>{formatPrice(price)}</span>
            {priceChange !== undefined && (
                <span
                    className={cn(
                        "flex items-center gap-0.5",
                        sizeClasses[size].change,
                        isPositive && "text-green-500",
                        isNegative && "text-red-500",
                        isNeutral && "text-muted-foreground"
                    )}
                >
                    {showIcon && (
                        <>
                            {isPositive && <TrendingUp className="h-3 w-3" />}
                            {isNegative && <TrendingDown className="h-3 w-3" />}
                            {isNeutral && <Minus className="h-3 w-3" />}
                        </>
                    )}
                    {formatPercent(priceChange)}
                </span>
            )}
        </div>
    );
}

