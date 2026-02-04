import { useState } from "react";
import { cn } from "~/lib/utils";
import { Bell, BellOff, Volume2, VolumeX, Clock, Filter, ChevronRight } from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface NotificationSettings {
    enabled: boolean;
    sound: boolean;
    quietHoursEnabled: boolean;
    quietHoursStart: string;
    quietHoursEnd: string;
    groupNotifications: boolean;
    priorities: {
        high: boolean;
        medium: boolean;
        low: boolean;
    };
    categories: {
        priceAlerts: boolean;
        whaleActivity: boolean;
        rugPullWarnings: boolean;
        portfolioUpdates: boolean;
        newsAlerts: boolean;
    };
}

export interface NotificationSettingsPanelProps {
    settings: NotificationSettings;
    onSettingsChange: (settings: NotificationSettings) => void;
    className?: string;
}

const DEFAULT_SETTINGS: NotificationSettings = {
    enabled: true,
    sound: true,
    quietHoursEnabled: false,
    quietHoursStart: "22:00",
    quietHoursEnd: "08:00",
    groupNotifications: true,
    priorities: {
        high: true,
        medium: true,
        low: false,
    },
    categories: {
        priceAlerts: true,
        whaleActivity: true,
        rugPullWarnings: true,
        portfolioUpdates: true,
        newsAlerts: false,
    },
};

/**
 * NotificationSettingsPanel - Configure notification preferences
 * Part of Epic 4.4 - Smart Notifications
 */
export function NotificationSettingsPanel({
    settings = DEFAULT_SETTINGS,
    onSettingsChange,
    className,
}: NotificationSettingsPanelProps) {
    const updateSettings = (partial: Partial<NotificationSettings>) => {
        onSettingsChange({ ...settings, ...partial });
    };

    const updatePriority = (key: keyof NotificationSettings["priorities"], value: boolean) => {
        onSettingsChange({
            ...settings,
            priorities: { ...settings.priorities, [key]: value },
        });
    };

    const updateCategory = (key: keyof NotificationSettings["categories"], value: boolean) => {
        onSettingsChange({
            ...settings,
            categories: { ...settings.categories, [key]: value },
        });
    };

    return (
        <div className={cn("rounded-lg border bg-card p-4 space-y-4", className)}>
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Bell className="h-5 w-5 text-primary" />
                    <span className="font-medium">Notification Settings</span>
                </div>
                <Button
                    variant={settings.enabled ? "default" : "outline"}
                    size="sm"
                    onClick={() => updateSettings({ enabled: !settings.enabled })}
                >
                    {settings.enabled ? (
                        <>
                            <Bell className="h-4 w-4 mr-1" /> On
                        </>
                    ) : (
                        <>
                            <BellOff className="h-4 w-4 mr-1" /> Off
                        </>
                    )}
                </Button>
            </div>

            {settings.enabled && (
                <>
                    {/* Sound Toggle */}
                    <div className="flex items-center justify-between py-2 border-b">
                        <div className="flex items-center gap-2">
                            {settings.sound ? (
                                <Volume2 className="h-4 w-4 text-muted-foreground" />
                            ) : (
                                <VolumeX className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span className="text-sm">Sound</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => updateSettings({ sound: !settings.sound })}
                        >
                            {settings.sound ? "On" : "Off"}
                        </Button>
                    </div>

                    {/* Quiet Hours */}
                    <div className="space-y-2 py-2 border-b">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Clock className="h-4 w-4 text-muted-foreground" />
                                <span className="text-sm">Quiet Hours</span>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => updateSettings({ quietHoursEnabled: !settings.quietHoursEnabled })}
                            >
                                {settings.quietHoursEnabled ? "On" : "Off"}
                            </Button>
                        </div>
                        {settings.quietHoursEnabled && (
                            <div className="flex items-center gap-2 ml-6 text-xs text-muted-foreground">
                                <input
                                    type="time"
                                    value={settings.quietHoursStart}
                                    onChange={(e) => updateSettings({ quietHoursStart: e.target.value })}
                                    className="bg-muted rounded px-2 py-1"
                                />
                                <span>to</span>
                                <input
                                    type="time"
                                    value={settings.quietHoursEnd}
                                    onChange={(e) => updateSettings({ quietHoursEnd: e.target.value })}
                                    className="bg-muted rounded px-2 py-1"
                                />
                            </div>
                        )}
                    </div>

                    {/* Priority Levels */}
                    <div className="space-y-2 py-2 border-b">
                        <div className="flex items-center gap-2 mb-2">
                            <Filter className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm font-medium">Priority Levels</span>
                        </div>
                        <div className="space-y-1 ml-6">
                            {(["high", "medium", "low"] as const).map((priority) => (
                                <label key={priority} className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={settings.priorities[priority]}
                                        onChange={(e) => updatePriority(priority, e.target.checked)}
                                        className="rounded"
                                    />
                                    <span className={cn(
                                        "text-xs capitalize",
                                        priority === "high" && "text-red-500",
                                        priority === "medium" && "text-yellow-500",
                                        priority === "low" && "text-muted-foreground"
                                    )}>
                                        {priority}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Categories */}
                    <div className="space-y-2 py-2">
                        <span className="text-sm font-medium">Categories</span>
                        <div className="space-y-1">
                            {Object.entries(settings.categories).map(([key, value]) => (
                                <label key={key} className="flex items-center justify-between cursor-pointer py-1">
                                    <span className="text-xs text-muted-foreground">
                                        {key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}
                                    </span>
                                    <input
                                        type="checkbox"
                                        checked={value}
                                        onChange={(e) => updateCategory(key as keyof NotificationSettings["categories"], e.target.checked)}
                                        className="rounded"
                                    />
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Group Notifications */}
                    <div className="flex items-center justify-between pt-2 border-t">
                        <span className="text-sm">Group similar notifications</span>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => updateSettings({ groupNotifications: !settings.groupNotifications })}
                        >
                            {settings.groupNotifications ? "On" : "Off"}
                        </Button>
                    </div>
                </>
            )}
        </div>
    );
}

