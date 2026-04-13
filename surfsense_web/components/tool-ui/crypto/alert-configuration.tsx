"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { z } from "zod";
import { cn } from "@/lib/utils";
import { Bell, TrendingUp, TrendingDown, Percent, DollarSign, Activity, Trash2, Edit2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

// Schema for alert configuration
const AlertConfigSchema = z.object({
    id: z.string(),
    type: z.enum(["price_above", "price_below", "percent_change", "volume_spike", "whale_activity"]),
    value: z.number(),
    enabled: z.boolean(),
});

// Schema for alert configuration tool arguments
export const AlertConfigurationArgsSchema = z.object({
    tokenSymbol: z.string(),
    tokenName: z.string().optional(),
    alerts: z.array(AlertConfigSchema),
});

export type AlertConfigurationArgs = z.infer<typeof AlertConfigurationArgsSchema>;

// Schema for alert configuration result
export const AlertConfigurationResultSchema = z.object({
    success: z.boolean(),
    message: z.string().optional(),
});

export type AlertConfigurationResult = z.infer<typeof AlertConfigurationResultSchema>;

const ALERT_TYPE_CONFIG = {
    price_above: { icon: TrendingUp, label: "Price Above", color: "text-green-500" },
    price_below: { icon: TrendingDown, label: "Price Below", color: "text-red-500" },
    percent_change: { icon: Percent, label: "% Change", color: "text-blue-500" },
    volume_spike: { icon: Activity, label: "Volume Spike", color: "text-purple-500" },
    whale_activity: { icon: DollarSign, label: "Whale Activity", color: "text-orange-500" },
};

const formatValue = (type: string, value: number): string => {
    if (type === "percent_change") return `${value > 0 ? "+" : ""}${value}%`;
    if (type === "volume_spike") return `${value}x normal`;
    if (type === "whale_activity") return `>${value.toLocaleString()} USD`;
    return `$${value < 1 ? value.toFixed(6) : value.toLocaleString()}`;
};

/**
 * AlertConfigurationToolUI - Displays/edits alert configurations for a token
 * Used when AI responds to "set alert for BULLA" or "show my alerts for BULLA"
 */
export const AlertConfigurationToolUI = makeAssistantToolUI<AlertConfigurationArgs, AlertConfigurationResult>({
    toolName: "configure_alerts",
    render: ({ args, status }) => {
        const isLoading = status.type === "running";
        const alerts = args.alerts || [];
        const enabledCount = alerts.filter(a => a.enabled).length;

        return (
            <Card className="my-3 overflow-hidden">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Bell className="h-5 w-5 text-blue-500" />
                            Alerts for {args.tokenSymbol}
                            <Badge variant="secondary">{enabledCount} active</Badge>
                            {isLoading && <Badge variant="outline" className="animate-pulse">Loading...</Badge>}
                        </div>
                        <Button variant="outline" size="sm">
                            <Bell className="h-4 w-4 mr-1" />
                            Add Alert
                        </Button>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                    {alerts.length === 0 ? (
                        <div className="py-6 text-center text-muted-foreground">
                            <Bell className="h-10 w-10 mx-auto mb-2 opacity-50" />
                            <p>No alerts configured</p>
                            <p className="text-sm">Say "Alert me if {args.tokenSymbol} drops 20%"</p>
                        </div>
                    ) : (
                        <div className="divide-y">
                            {alerts.map((alert) => {
                                const config = ALERT_TYPE_CONFIG[alert.type];
                                const Icon = config.icon;
                                return (
                                    <div key={alert.id} className="flex items-center justify-between py-3">
                                        <div className="flex items-center gap-3">
                                            <Icon className={cn("h-4 w-4", config.color)} />
                                            <div>
                                                <p className="font-medium">{config.label}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    {formatValue(alert.type, alert.value)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Switch checked={alert.enabled} />
                                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                                <Edit2 className="h-3 w-3" />
                                            </Button>
                                            <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500">
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>
        );
    },
});

