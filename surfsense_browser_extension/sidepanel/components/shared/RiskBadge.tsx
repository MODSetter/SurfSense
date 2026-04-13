import { cn } from "~/lib/utils";
import { Shield, AlertTriangle, XCircle, CheckCircle } from "lucide-react";

export type RiskLevel = "safe" | "low" | "medium" | "high" | "critical";

export interface RiskBadgeProps {
    /** Risk level */
    level: RiskLevel;
    /** Optional score (0-100) */
    score?: number;
    /** Show score value */
    showScore?: boolean;
    /** Size variant */
    size?: "sm" | "md" | "lg";
    /** Additional class names */
    className?: string;
}

// Risk level configuration
const RISK_CONFIG: Record<RiskLevel, {
    label: string;
    color: string;
    bgColor: string;
    borderColor: string;
    Icon: typeof Shield;
}> = {
    safe: {
        label: "Safe",
        color: "text-green-600 dark:text-green-400",
        bgColor: "bg-green-500/10",
        borderColor: "border-green-500/30",
        Icon: CheckCircle,
    },
    low: {
        label: "Low Risk",
        color: "text-green-500 dark:text-green-400",
        bgColor: "bg-green-500/10",
        borderColor: "border-green-500/30",
        Icon: Shield,
    },
    medium: {
        label: "Medium",
        color: "text-yellow-600 dark:text-yellow-400",
        bgColor: "bg-yellow-500/10",
        borderColor: "border-yellow-500/30",
        Icon: AlertTriangle,
    },
    high: {
        label: "High Risk",
        color: "text-orange-600 dark:text-orange-400",
        bgColor: "bg-orange-500/10",
        borderColor: "border-orange-500/30",
        Icon: AlertTriangle,
    },
    critical: {
        label: "Critical",
        color: "text-red-600 dark:text-red-400",
        bgColor: "bg-red-500/10",
        borderColor: "border-red-500/30",
        Icon: XCircle,
    },
};

/**
 * RiskBadge - Displays risk level with color-coded badge
 * 
 * Features:
 * - Color-coded risk levels (safe to critical)
 * - Optional score display
 * - Multiple size variants
 * - Accessible with proper ARIA labels
 */
export function RiskBadge({
    level,
    score,
    showScore = false,
    size = "md",
    className,
}: RiskBadgeProps) {
    const config = RISK_CONFIG[level];
    const { Icon } = config;

    const sizeClasses = {
        sm: "px-1.5 py-0.5 text-xs gap-1",
        md: "px-2 py-1 text-sm gap-1.5",
        lg: "px-3 py-1.5 text-base gap-2",
    };

    const iconSizes = {
        sm: "h-3 w-3",
        md: "h-4 w-4",
        lg: "h-5 w-5",
    };

    return (
        <div
            className={cn(
                "inline-flex items-center rounded-full border font-medium",
                config.bgColor,
                config.borderColor,
                config.color,
                sizeClasses[size],
                className
            )}
            role="status"
            aria-label={`Risk level: ${config.label}${score !== undefined ? `, Score: ${score}` : ""}`}
        >
            <Icon className={iconSizes[size]} />
            <span>{config.label}</span>
            {showScore && score !== undefined && (
                <span className="font-bold">({score})</span>
            )}
        </div>
    );
}

/**
 * Get risk level from score (0-100)
 */
export function getRiskLevelFromScore(score: number): RiskLevel {
    if (score >= 80) return "safe";
    if (score >= 60) return "low";
    if (score >= 40) return "medium";
    if (score >= 20) return "high";
    return "critical";
}

