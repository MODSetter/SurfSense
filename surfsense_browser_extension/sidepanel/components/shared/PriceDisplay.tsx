import { cn } from "~/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export interface PriceDisplayProps {
    /** Current price value */
    price: string | number;
    /** Price change percentage (positive = up, negative = down) */
    priceChange?: number;
    /** Show the change indicator arrow */
    showChangeIndicator?: boolean;
    /** Size variant */
    size?: "sm" | "md" | "lg";
    /** Additional class names */
    className?: string;
}

/**
 * PriceDisplay - Shows price with optional change indicator
 * 
 * Features:
 * - Color-coded price changes (green for up, red for down)
 * - Animated arrow indicators
 * - Multiple size variants
 */
export function PriceDisplay({
    price,
    priceChange,
    showChangeIndicator = true,
    size = "md",
    className,
}: PriceDisplayProps) {
    const isPositive = priceChange !== undefined && priceChange > 0;
    const isNegative = priceChange !== undefined && priceChange < 0;
    const isNeutral = priceChange === undefined || priceChange === 0;

    const sizeClasses = {
        sm: "text-sm",
        md: "text-base",
        lg: "text-xl font-semibold",
    };

    const changeClasses = {
        sm: "text-xs",
        md: "text-sm",
        lg: "text-base",
    };

    const iconSizes = {
        sm: "h-3 w-3",
        md: "h-4 w-4",
        lg: "h-5 w-5",
    };

    const formatPrice = (value: string | number): string => {
        if (typeof value === "string") return value;
        if (value < 0.00001) return `$${value.toExponential(2)}`;
        if (value < 1) return `$${value.toFixed(6)}`;
        if (value < 1000) return `$${value.toFixed(2)}`;
        return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    };

    const formatChange = (change: number): string => {
        const sign = change > 0 ? "+" : "";
        return `${sign}${change.toFixed(2)}%`;
    };

    return (
        <div className={cn("flex items-center gap-2", className)}>
            {/* Price */}
            <span className={cn("font-medium", sizeClasses[size])}>
                {formatPrice(price)}
            </span>

            {/* Change indicator */}
            {showChangeIndicator && priceChange !== undefined && (
                <div
                    className={cn(
                        "flex items-center gap-0.5",
                        changeClasses[size],
                        isPositive && "text-green-500",
                        isNegative && "text-red-500",
                        isNeutral && "text-muted-foreground"
                    )}
                >
                    {isPositive && <TrendingUp className={iconSizes[size]} />}
                    {isNegative && <TrendingDown className={iconSizes[size]} />}
                    {isNeutral && <Minus className={iconSizes[size]} />}
                    <span>{formatChange(priceChange)}</span>
                </div>
            )}
        </div>
    );
}

