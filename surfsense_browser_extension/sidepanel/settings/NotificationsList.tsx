import { cn } from "~/lib/utils";
import { Bell, AlertTriangle, TrendingUp, TrendingDown, Wallet, Fish, X, Check } from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface Notification {
    id: string;
    type: "price_alert" | "whale_activity" | "rug_warning" | "portfolio" | "news";
    priority: "high" | "medium" | "low";
    title: string;
    message: string;
    tokenSymbol?: string;
    timestamp: Date;
    read: boolean;
    actionUrl?: string;
}

export interface NotificationsListProps {
    notifications: Notification[];
    onMarkRead: (id: string) => void;
    onMarkAllRead: () => void;
    onDismiss: (id: string) => void;
    onNotificationClick?: (notification: Notification) => void;
    className?: string;
}

const getNotificationIcon = (type: Notification["type"]) => {
    switch (type) {
        case "price_alert":
            return <TrendingUp className="h-4 w-4" />;
        case "whale_activity":
            return <Fish className="h-4 w-4" />;
        case "rug_warning":
            return <AlertTriangle className="h-4 w-4" />;
        case "portfolio":
            return <Wallet className="h-4 w-4" />;
        case "news":
            return <Bell className="h-4 w-4" />;
        default:
            return <Bell className="h-4 w-4" />;
    }
};

const getPriorityColor = (priority: Notification["priority"]) => {
    switch (priority) {
        case "high":
            return "border-l-red-500 bg-red-500/5";
        case "medium":
            return "border-l-yellow-500 bg-yellow-500/5";
        case "low":
            return "border-l-muted-foreground bg-muted/30";
        default:
            return "border-l-muted-foreground";
    }
};

const formatTime = (date: Date): string => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
};

/**
 * NotificationsList - Display and manage notifications
 * Part of Epic 4.4 - Smart Notifications
 */
export function NotificationsList({
    notifications,
    onMarkRead,
    onMarkAllRead,
    onDismiss,
    onNotificationClick,
    className,
}: NotificationsListProps) {
    const unreadCount = notifications.filter((n) => !n.read).length;

    return (
        <div className={cn("rounded-lg border bg-card", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b">
                <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-primary" />
                    <span className="font-medium text-sm">Notifications</span>
                    {unreadCount > 0 && (
                        <span className="bg-primary text-primary-foreground text-xs px-1.5 py-0.5 rounded-full">
                            {unreadCount}
                        </span>
                    )}
                </div>
                {unreadCount > 0 && (
                    <Button variant="ghost" size="sm" className="text-xs" onClick={onMarkAllRead}>
                        <Check className="h-3 w-3 mr-1" />
                        Mark all read
                    </Button>
                )}
            </div>

            {/* Notifications List */}
            <div className="max-h-[400px] overflow-y-auto">
                {notifications.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground text-sm">
                        <Bell className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>No notifications yet</p>
                    </div>
                ) : (
                    notifications.map((notification) => (
                        <div
                            key={notification.id}
                            className={cn(
                                "flex items-start gap-3 p-3 border-b border-l-2 cursor-pointer hover:bg-muted/50 transition-colors",
                                getPriorityColor(notification.priority),
                                !notification.read && "bg-primary/5"
                            )}
                            onClick={() => {
                                if (!notification.read) onMarkRead(notification.id);
                                onNotificationClick?.(notification);
                            }}
                        >
                            <div className={cn(
                                "p-1.5 rounded-full",
                                notification.type === "rug_warning" ? "bg-red-500/20 text-red-500" :
                                notification.type === "whale_activity" ? "bg-blue-500/20 text-blue-500" :
                                notification.type === "price_alert" ? "bg-green-500/20 text-green-500" :
                                "bg-muted text-muted-foreground"
                            )}>
                                {getNotificationIcon(notification.type)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className={cn("text-sm font-medium", !notification.read && "text-foreground")}>
                                        {notification.title}
                                    </span>
                                    {notification.tokenSymbol && (
                                        <span className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                            {notification.tokenSymbol}
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                                    {notification.message}
                                </p>
                                <span className="text-[10px] text-muted-foreground mt-1 block">
                                    {formatTime(notification.timestamp)}
                                </span>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDismiss(notification.id);
                                }}
                            >
                                <X className="h-3 w-3" />
                            </Button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

