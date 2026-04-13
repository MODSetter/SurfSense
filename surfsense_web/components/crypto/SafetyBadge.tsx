"use client";

import { cn } from "@/lib/utils";
import { Shield, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import { getSafetyLabel } from "@/lib/mock/cryptoMockData";

interface SafetyBadgeProps {
    score: number;
    size?: "sm" | "md" | "lg";
    showScore?: boolean;
    className?: string;
}

const sizeClasses = {
    sm: { badge: "px-1.5 py-0.5 text-xs", icon: "h-3 w-3" },
    md: { badge: "px-2 py-1 text-sm", icon: "h-4 w-4" },
    lg: { badge: "px-3 py-1.5 text-base", icon: "h-5 w-5" },
};

function getScoreConfig(score: number) {
    if (score >= 80) {
        return {
            color: "bg-green-500/10 text-green-600 border-green-500/20",
            Icon: ShieldCheck,
        };
    }
    if (score >= 60) {
        return {
            color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
            Icon: Shield,
        };
    }
    if (score >= 40) {
        return {
            color: "bg-orange-500/10 text-orange-600 border-orange-500/20",
            Icon: ShieldAlert,
        };
    }
    return {
        color: "bg-red-500/10 text-red-600 border-red-500/20",
        Icon: ShieldX,
    };
}

export function SafetyBadge({ score, size = "md", showScore = true, className }: SafetyBadgeProps) {
    const { color, Icon } = getScoreConfig(score);
    const label = getSafetyLabel(score);

    return (
        <div
            className={cn(
                "inline-flex items-center gap-1 rounded-full border font-medium",
                color,
                sizeClasses[size].badge,
                className
            )}
        >
            <Icon className={sizeClasses[size].icon} />
            <span>{label}</span>
            {showScore && <span className="opacity-70">({score})</span>}
        </div>
    );
}

