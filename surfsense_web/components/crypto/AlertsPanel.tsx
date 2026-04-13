"use client";

import { cn } from "@/lib/utils";
import { Bell, BellOff, Check, AlertTriangle, Info, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChainIcon } from "./ChainIcon";
import type { Alert } from "@/lib/mock/cryptoMockData";

interface AlertsPanelProps {
    alerts: Alert[];
    onAlertClick?: (alert: Alert) => void;
    onMarkAsRead?: (alertId: string) => void;
    onMarkAllAsRead?: () => void;
    onDismiss?: (alertId: string) => void;
    className?: string;
}

function formatTimeAgo(date: Date): string {
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function getSeverityConfig(severity: Alert["severity"]) {
    switch (severity) {
        case "critical":
            return {
                icon: XCircle,
                color: "text-red-500",
                bg: "bg-red-500/10",
                border: "border-red-500/20",
            };
        case "warning":
            return {
                icon: AlertTriangle,
                color: "text-yellow-500",
                bg: "bg-yellow-500/10",
                border: "border-yellow-500/20",
            };
        default:
            return {
                icon: Info,
                color: "text-blue-500",
                bg: "bg-blue-500/10",
                border: "border-blue-500/20",
            };
    }
}

function AlertItem({
    alert,
    onClick,
    onMarkAsRead,
    onDismiss,
}: {
    alert: Alert;
    onClick?: () => void;
    onMarkAsRead?: () => void;
    onDismiss?: () => void;
}) {
    const config = getSeverityConfig(alert.severity);
    const Icon = config.icon;

    return (
        <div
            className={cn(
                "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                config.bg,
                config.border,
                !alert.isRead && "ring-1 ring-primary/20",
                "hover:bg-muted/50"
            )}
            onClick={onClick}
        >
            <div className={cn("mt-0.5", config.color)}>
                <Icon className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                    <ChainIcon chain={alert.chain} size="sm" />
                    <span className="font-medium text-sm">{alert.tokenSymbol}</span>
                    {!alert.isRead && (
                        <Badge variant="default" className="h-4 px-1 text-[10px]">NEW</Badge>
                    )}
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2">{alert.message}</p>
                <p className="text-xs text-muted-foreground mt-1">{formatTimeAgo(alert.timestamp)}</p>
            </div>
            <div className="flex flex-col gap-1">
                {!alert.isRead && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={(e) => {
                            e.stopPropagation();
                            onMarkAsRead?.();
                        }}
                        title="Mark as read"
                    >
                        <Check className="h-3 w-3" />
                    </Button>
                )}
            </div>
        </div>
    );
}

export function AlertsPanel({
    alerts,
    onAlertClick,
    onMarkAsRead,
    onMarkAllAsRead,
    onDismiss,
    className,
}: AlertsPanelProps) {
    const unreadCount = alerts.filter((a) => !a.isRead).length;

    return (
        <Card className={cn("", className)}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Bell className="h-5 w-5" /> Alerts
                        {unreadCount > 0 && (
                            <Badge variant="destructive" className="ml-1">{unreadCount}</Badge>
                        )}
                    </CardTitle>
                    {unreadCount > 0 && (
                        <Button variant="ghost" size="sm" onClick={onMarkAllAsRead}>
                            <Check className="mr-1 h-3 w-3" />
                            Mark all read
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                {alerts.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                        <BellOff className="h-8 w-8 mb-2" />
                        <p className="text-sm">No alerts yet</p>
                        <p className="text-xs">Configure alerts on your watchlist tokens</p>
                    </div>
                ) : (
                    <ScrollArea className="h-[400px] pr-4">
                        <div className="space-y-2">
                            {alerts.map((alert) => (
                                <AlertItem
                                    key={alert.id}
                                    alert={alert}
                                    onClick={() => onAlertClick?.(alert)}
                                    onMarkAsRead={() => onMarkAsRead?.(alert.id)}
                                    onDismiss={() => onDismiss?.(alert.id)}
                                />
                            ))}
                        </div>
                    </ScrollArea>
                )}
            </CardContent>
        </Card>
    );
}

