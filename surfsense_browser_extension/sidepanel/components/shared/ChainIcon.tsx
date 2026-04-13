import { cn } from "~/lib/utils";

export type ChainType = "solana" | "ethereum" | "base" | "arbitrum" | "polygon" | "bsc" | "avalanche" | "unknown";

export interface ChainIconProps {
    /** Blockchain chain identifier */
    chain: ChainType | string;
    /** Size of the icon */
    size?: "sm" | "md" | "lg";
    /** Show chain name label */
    showLabel?: boolean;
    /** Additional class names */
    className?: string;
}

// Chain configuration with colors and display names
const CHAIN_CONFIG: Record<string, { color: string; bgColor: string; label: string; emoji: string }> = {
    solana: {
        color: "#9945FF",
        bgColor: "bg-purple-500/10",
        label: "Solana",
        emoji: "◎",
    },
    ethereum: {
        color: "#627EEA",
        bgColor: "bg-blue-500/10",
        label: "Ethereum",
        emoji: "Ξ",
    },
    base: {
        color: "#0052FF",
        bgColor: "bg-blue-600/10",
        label: "Base",
        emoji: "🔵",
    },
    arbitrum: {
        color: "#28A0F0",
        bgColor: "bg-sky-500/10",
        label: "Arbitrum",
        emoji: "🔷",
    },
    polygon: {
        color: "#8247E5",
        bgColor: "bg-violet-500/10",
        label: "Polygon",
        emoji: "⬡",
    },
    bsc: {
        color: "#F0B90B",
        bgColor: "bg-yellow-500/10",
        label: "BSC",
        emoji: "🟡",
    },
    avalanche: {
        color: "#E84142",
        bgColor: "bg-red-500/10",
        label: "Avalanche",
        emoji: "🔺",
    },
    unknown: {
        color: "#6B7280",
        bgColor: "bg-gray-500/10",
        label: "Unknown",
        emoji: "🔗",
    },
};

/**
 * ChainIcon - Displays blockchain chain icon with optional label
 * 
 * Features:
 * - Chain-specific colors and icons
 * - Multiple size variants
 * - Optional chain name label
 */
export function ChainIcon({
    chain,
    size = "md",
    showLabel = false,
    className,
}: ChainIconProps) {
    const normalizedChain = chain.toLowerCase();
    const config = CHAIN_CONFIG[normalizedChain] || CHAIN_CONFIG.unknown;

    const sizeClasses = {
        sm: "w-4 h-4 text-xs",
        md: "w-5 h-5 text-sm",
        lg: "w-6 h-6 text-base",
    };

    const labelSizes = {
        sm: "text-xs",
        md: "text-sm",
        lg: "text-base",
    };

    return (
        <div className={cn("flex items-center gap-1.5", className)}>
            <div
                className={cn(
                    "rounded-full flex items-center justify-center",
                    config.bgColor,
                    sizeClasses[size]
                )}
                style={{ color: config.color }}
                title={config.label}
            >
                <span>{config.emoji}</span>
            </div>
            {showLabel && (
                <span
                    className={cn("font-medium", labelSizes[size])}
                    style={{ color: config.color }}
                >
                    {config.label}
                </span>
            )}
        </div>
    );
}

/**
 * Get chain color for custom styling
 */
export function getChainColor(chain: string): string {
    const normalizedChain = chain.toLowerCase();
    return CHAIN_CONFIG[normalizedChain]?.color || CHAIN_CONFIG.unknown.color;
}

