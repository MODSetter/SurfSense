"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { AlertTriangle, TrendingUp, TrendingDown, Activity, Zap, Eye, Bell, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Schema for proactive alert tool arguments
export const ProactiveAlertArgsSchema = z.object({
    alertType: z.enum(["price_surge", "price_drop", "whale_buy", "whale_sell", "volume_spike", "safety_warning"]),
    tokenSymbol: z.string(),
    tokenName: z.string().optional(),
    value: z.number(),
    previousValue: z.number().optional(),
    message: z.string(),
    severity: z.enum(["info", "warning", "critical"]).optional(),
    timestamp: z.string().optional(),
});

export type ProactiveAlertArgs = z.infer<typeof ProactiveAlertArgsSchema>;

// Schema for proactive alert result
export const ProactiveAlertResultSchema = z.object({
    acknowledged: z.boolean(),
});

export type ProactiveAlertResult = z.infer<typeof ProactiveAlertResultSchema>;

const ALERT_TYPE_CONFIG = {
    price_surge: { icon: TrendingUp, color: "text-green-500", bgColor: "bg-green-500/10", borderColor: "border-l-green-500" },
    price_drop: { icon: TrendingDown, color: "text-red-500", bgColor: "bg-red-500/10", borderColor: "border-l-red-500" },
    whale_buy: { icon: Zap, color: "text-green-500", bgColor: "bg-green-500/10", borderColor: "border-l-green-500" },
    whale_sell: { icon: Zap, color: "text-red-500", bgColor: "bg-red-500/10", borderColor: "border-l-red-500" },
    volume_spike: { icon: Activity, color: "text-purple-500", bgColor: "bg-purple-500/10", borderColor: "border-l-purple-500" },
    safety_warning: { icon: AlertTriangle, color: "text-yellow-500", bgColor: "bg-yellow-500/10", borderColor: "border-l-yellow-500" },
};

const SEVERITY_CONFIG = {
    info: { badge: "secondary", pulse: false },
    warning: { badge: "warning", pulse: false },
    critical: { badge: "destructive", pulse: true },
};

/**
 * ProactiveAlertToolUI - Displays AI-initiated alerts in chat
 * Used when AI proactively notifies user about price changes, whale activity, etc.
 */
export const ProactiveAlertToolUI = makeAssistantToolUI<ProactiveAlertArgs, ProactiveAlertResult>({
    toolName: "proactive_alert",
    render: ({ args, result }) => {
        const config = ALERT_TYPE_CONFIG[args.alertType];
        const severity = args.severity || "info";
        const severityConfig = SEVERITY_CONFIG[severity];
        const Icon = config.icon;
        const isAcknowledged = result?.acknowledged;

        const formatChange = () => {
            if (args.previousValue === undefined) return null;
            const change = ((args.value - args.previousValue) / args.previousValue) * 100;
            return change;
        };

        const change = formatChange();

        return (
            <Card className={cn(
                "my-3 overflow-hidden border-l-4 transition-all",
                config.borderColor,
                isAcknowledged && "opacity-60"
            )}>
                <CardContent className="py-4">
                    <div className="flex items-start gap-3">
                        {/* Alert Icon */}
                        <div className={cn(
                            "p-2 rounded-full",
                            config.bgColor,
                            severityConfig.pulse && "animate-pulse"
                        )}>
                            <Icon className={cn("h-5 w-5", config.color)} />
                        </div>

                        {/* Content */}
                        <div className="flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                                <Badge variant={severityConfig.badge as any} className="uppercase text-xs">
                                    {args.alertType.replace("_", " ")}
                                </Badge>
                                <span className="font-bold">{args.tokenSymbol}</span>
                                {change !== null && (
                                    <span className={cn(
                                        "font-medium",
                                        change >= 0 ? "text-green-500" : "text-red-500"
                                    )}>
                                        {change >= 0 ? "+" : ""}{change.toFixed(1)}%
                                    </span>
                                )}
                                {args.timestamp && (
                                    <span className="text-xs text-muted-foreground ml-auto">
                                        {args.timestamp}
                                    </span>
                                )}
                            </div>

                            <p className="mt-2 text-sm">{args.message}</p>
                        </div>

                        {/* Dismiss */}
                        {!isAcknowledged && (
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground">
                                <X className="h-4 w-4" />
                            </Button>
                        )}
                    </div>

                    {/* Action buttons */}
                    {!isAcknowledged && (
                        <div className="flex gap-2 mt-3 ml-11">
                            <Button variant="outline" size="sm">
                                <Eye className="h-3 w-3 mr-1" />
                                View Details
                            </Button>
                            <Button variant="outline" size="sm">
                                <Bell className="h-3 w-3 mr-1" />
                                Adjust Alert
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    },
});

