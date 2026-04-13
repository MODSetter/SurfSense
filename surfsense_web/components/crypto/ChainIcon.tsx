"use client";

import { cn } from "@/lib/utils";
import type { ChainType } from "@/lib/mock/cryptoMockData";

interface ChainIconProps {
    chain: ChainType;
    size?: "sm" | "md" | "lg";
    showName?: boolean;
    className?: string;
}

const chainConfig: Record<ChainType, { color: string; icon: string; name: string }> = {
    solana: { color: "#9945FF", icon: "◎", name: "Solana" },
    ethereum: { color: "#627EEA", icon: "Ξ", name: "Ethereum" },
    base: { color: "#0052FF", icon: "🔵", name: "Base" },
    arbitrum: { color: "#28A0F0", icon: "🔷", name: "Arbitrum" },
    polygon: { color: "#8247E5", icon: "⬡", name: "Polygon" },
    bsc: { color: "#F0B90B", icon: "⬢", name: "BNB Chain" },
};

const sizeClasses = {
    sm: "h-4 w-4 text-xs",
    md: "h-5 w-5 text-sm",
    lg: "h-6 w-6 text-base",
};

export function ChainIcon({ chain, size = "md", showName = false, className }: ChainIconProps) {
    const config = chainConfig[chain] || { color: "#888888", icon: "?", name: chain };

    return (
        <div className={cn("flex items-center gap-1.5", className)}>
            <span
                className={cn(
                    "flex items-center justify-center rounded-full",
                    sizeClasses[size]
                )}
                style={{ backgroundColor: `${config.color}20`, color: config.color }}
            >
                {config.icon}
            </span>
            {showName && (
                <span className="text-sm text-muted-foreground">{config.name}</span>
            )}
        </div>
    );
}

