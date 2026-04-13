import { cn } from "~/lib/utils";
import { ArrowRight, Sparkles, TrendingUp, Shield, Wallet } from "lucide-react";

export type SuggestionType = "general" | "safety" | "trending" | "wallet" | "custom";

export interface SuggestionCardProps {
    /** Suggestion text to display */
    text: string;
    /** Type of suggestion for icon selection */
    type?: SuggestionType;
    /** Custom icon (overrides type icon) */
    icon?: React.ReactNode;
    /** Click handler */
    onClick?: (text: string) => void;
    /** Disabled state */
    disabled?: boolean;
    /** Additional class names */
    className?: string;
}

// Suggestion type icons
const TYPE_ICONS: Record<SuggestionType, typeof Sparkles> = {
    general: Sparkles,
    safety: Shield,
    trending: TrendingUp,
    wallet: Wallet,
    custom: Sparkles,
};

/**
 * SuggestionCard - Clickable suggestion card for chat prompts
 * 
 * Features:
 * - Type-specific icons
 * - Hover animations
 * - Click to send suggestion
 * - Accessible keyboard navigation
 */
export function SuggestionCard({
    text,
    type = "general",
    icon,
    onClick,
    disabled = false,
    className,
}: SuggestionCardProps) {
    const Icon = TYPE_ICONS[type];

    const handleClick = () => {
        if (!disabled && onClick) {
            onClick(text);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleClick();
        }
    };

    return (
        <div
            role="button"
            tabIndex={disabled ? -1 : 0}
            onClick={handleClick}
            onKeyDown={handleKeyDown}
            className={cn(
                "group flex items-center gap-3 p-3 rounded-lg border",
                "bg-card hover:bg-accent/50 transition-all duration-200",
                "cursor-pointer select-none",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                disabled && "opacity-50 cursor-not-allowed",
                className
            )}
            aria-disabled={disabled}
        >
            {/* Icon */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                {icon || <Icon className="h-4 w-4" />}
            </div>

            {/* Text */}
            <span className="flex-1 text-sm text-foreground line-clamp-2">
                {text}
            </span>

            {/* Arrow indicator */}
            <ArrowRight
                className={cn(
                    "h-4 w-4 text-muted-foreground",
                    "opacity-0 -translate-x-2 transition-all duration-200",
                    "group-hover:opacity-100 group-hover:translate-x-0"
                )}
            />
        </div>
    );
}

/**
 * Default crypto-related suggestions
 */
export const DEFAULT_CRYPTO_SUGGESTIONS: Array<{ text: string; type: SuggestionType }> = [
    { text: "Is this token safe to invest in?", type: "safety" },
    { text: "What are the top gainers on Solana today?", type: "trending" },
    { text: "Analyze this wallet's trading history", type: "wallet" },
    { text: "Check for rug pull indicators", type: "safety" },
    { text: "What's the market sentiment for this token?", type: "general" },
];

