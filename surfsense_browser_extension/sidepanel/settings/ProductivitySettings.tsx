import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    Settings,
    Bell,
    BellOff,
    Clock,
    Keyboard,
    Menu,
    Save,
} from "lucide-react";
import { Button } from "@/routes/ui/button";

export interface NotificationSettings {
    enabled: boolean;
    priorities: {
        high: boolean;
        medium: boolean;
        low: boolean;
    };
    quietHours: {
        enabled: boolean;
        start: string;
        end: string;
    };
    groupNotifications: boolean;
    smartBatching: boolean;
}

export interface KeyboardShortcut {
    id: string;
    action: string;
    shortcut: string;
    description: string;
}

export interface QuickActionsSettings {
    contextMenuEnabled: boolean;
    autoDetectAddresses: boolean;
}

export interface ProductivitySettingsData {
    notifications: NotificationSettings;
    shortcuts: KeyboardShortcut[];
    quickActions: QuickActionsSettings;
}

export interface ProductivitySettingsPanelProps {
    /** Current settings */
    settings?: ProductivitySettingsData;
    /** Callback when settings are saved */
    onSave?: (settings: ProductivitySettingsData) => void;
    /** Additional class names */
    className?: string;
}

/**
 * ProductivitySettingsPanel - Productivity settings management
 *
 * Features:
 * - Notification settings (priorities, quiet hours, grouping)
 * - Keyboard shortcuts configuration
 * - Quick actions settings (context menu, auto-detect)
 * - Per-token notification settings
 */
export function ProductivitySettingsPanel({
    settings: initialSettings,
    onSave,
    className,
}: ProductivitySettingsPanelProps) {
    const [settings, setSettings] = useState<ProductivitySettingsData>(
        initialSettings || {
            notifications: {
                enabled: true,
                priorities: {
                    high: true,
                    medium: true,
                    low: false,
                },
                quietHours: {
                    enabled: true,
                    start: "23:00",
                    end: "07:00",
                },
                groupNotifications: true,
                smartBatching: true,
            },
            shortcuts: [
                { id: "open-panel", action: "Open Side Panel", shortcut: "Cmd+Shift+S", description: "Open/close the side panel" },
                { id: "new-chat", action: "New Chat", shortcut: "Cmd+Shift+N", description: "Start a new chat" },
                { id: "analyze-token", action: "Analyze Token", shortcut: "Cmd+Shift+A", description: "Analyze current token" },
                { id: "add-watchlist", action: "Add to Watchlist", shortcut: "Cmd+Shift+W", description: "Add token to watchlist" },
                { id: "capture-chart", action: "Capture Chart", shortcut: "Cmd+Shift+C", description: "Capture chart screenshot" },
                { id: "open-portfolio", action: "Open Portfolio", shortcut: "Cmd+Shift+P", description: "Open portfolio panel" },
            ],
            quickActions: {
                contextMenuEnabled: true,
                autoDetectAddresses: true,
            },
        }
    );

    const [hasChanges, setHasChanges] = useState(false);

    const updateSettings = (updates: Partial<ProductivitySettingsData>) => {
        setSettings({ ...settings, ...updates });
        setHasChanges(true);
    };

    const handleSave = () => {
        onSave?.(settings);
        setHasChanges(false);
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <Settings className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">Productivity Settings</h2>
                        <p className="text-xs text-muted-foreground">
                            Notifications, shortcuts, and quick actions
                        </p>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Notifications */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Bell className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Notifications</h3>
                    </div>

                    {/* Enable/Disable */}
                    <label className="flex items-center justify-between cursor-pointer">
                        <span className="text-sm">Enable notifications</span>
                        <input
                            type="checkbox"
                            checked={settings.notifications.enabled}
                            onChange={(e) =>
                                updateSettings({
                                    notifications: {
                                        ...settings.notifications,
                                        enabled: e.target.checked,
                                    },
                                })
                            }
                            className="rounded"
                        />
                    </label>

                    {/* Priority Levels */}
                    <div className="space-y-2">
                        <label className="text-xs font-semibold text-muted-foreground">Priority Levels</label>
                        <div className="space-y-2 pl-4">
                            {(["high", "medium", "low"] as const).map((priority) => (
                                <label key={priority} className="flex items-center justify-between cursor-pointer">
                                    <span className="text-sm capitalize">{priority}</span>
                                    <input
                                        type="checkbox"
                                        checked={settings.notifications.priorities[priority]}
                                        onChange={(e) =>
                                            updateSettings({
                                                notifications: {
                                                    ...settings.notifications,
                                                    priorities: {
                                                        ...settings.notifications.priorities,
                                                        [priority]: e.target.checked,
                                                    },
                                                },
                                            })
                                        }
                                        className="rounded"
                                        disabled={!settings.notifications.enabled}
                                    />
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Quiet Hours */}
                    <div className="space-y-2">
                        <label className="flex items-center justify-between cursor-pointer">
                            <div className="flex items-center gap-2">
                                <Clock className="h-3 w-3 text-muted-foreground" />
                                <span className="text-sm">Quiet Hours</span>
                            </div>
                            <input
                                type="checkbox"
                                checked={settings.notifications.quietHours.enabled}
                                onChange={(e) =>
                                    updateSettings({
                                        notifications: {
                                            ...settings.notifications,
                                            quietHours: {
                                                ...settings.notifications.quietHours,
                                                enabled: e.target.checked,
                                            },
                                        },
                                    })
                                }
                                className="rounded"
                                disabled={!settings.notifications.enabled}
                            />
                        </label>
                        {settings.notifications.quietHours.enabled && (
                            <div className="flex gap-2 pl-6">
                                <input
                                    type="time"
                                    value={settings.notifications.quietHours.start}
                                    onChange={(e) =>
                                        updateSettings({
                                            notifications: {
                                                ...settings.notifications,
                                                quietHours: {
                                                    ...settings.notifications.quietHours,
                                                    start: e.target.value,
                                                },
                                            },
                                        })
                                    }
                                    className="flex-1 p-1 text-xs border rounded"
                                />
                                <span className="text-xs text-muted-foreground">to</span>
                                <input
                                    type="time"
                                    value={settings.notifications.quietHours.end}
                                    onChange={(e) =>
                                        updateSettings({
                                            notifications: {
                                                ...settings.notifications,
                                                quietHours: {
                                                    ...settings.notifications.quietHours,
                                                    end: e.target.value,
                                                },
                                            },
                                        })
                                    }
                                    className="flex-1 p-1 text-xs border rounded"
                                />
                            </div>
                        )}
                    </div>

                    {/* Grouping Options */}
                    <div className="space-y-2">
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm">Group notifications</span>
                            <input
                                type="checkbox"
                                checked={settings.notifications.groupNotifications}
                                onChange={(e) =>
                                    updateSettings({
                                        notifications: {
                                            ...settings.notifications,
                                            groupNotifications: e.target.checked,
                                        },
                                    })
                                }
                                className="rounded"
                                disabled={!settings.notifications.enabled}
                            />
                        </label>
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm">Smart batching (5+ alerts)</span>
                            <input
                                type="checkbox"
                                checked={settings.notifications.smartBatching}
                                onChange={(e) =>
                                    updateSettings({
                                        notifications: {
                                            ...settings.notifications,
                                            smartBatching: e.target.checked,
                                        },
                                    })
                                }
                                className="rounded"
                                disabled={!settings.notifications.enabled}
                            />
                        </label>
                    </div>
                </div>

                {/* Keyboard Shortcuts */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Keyboard className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Keyboard Shortcuts</h3>
                    </div>
                    <div className="space-y-2">
                        {settings.shortcuts.map((shortcut) => (
                            <div
                                key={shortcut.id}
                                className="flex items-center justify-between p-2 bg-muted/50 rounded"
                            >
                                <div>
                                    <div className="text-sm font-medium">{shortcut.action}</div>
                                    <div className="text-xs text-muted-foreground">{shortcut.description}</div>
                                </div>
                                <kbd className="px-2 py-1 text-xs font-mono bg-background border rounded">
                                    {shortcut.shortcut}
                                </kbd>
                            </div>
                        ))}
                    </div>
                    <Button variant="outline" size="sm" className="w-full">
                        Customize Shortcuts
                    </Button>
                </div>

                {/* Quick Actions */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Menu className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Quick Actions</h3>
                    </div>
                    <div className="space-y-2">
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm">Context menu enabled</span>
                            <input
                                type="checkbox"
                                checked={settings.quickActions.contextMenuEnabled}
                                onChange={(e) =>
                                    updateSettings({
                                        quickActions: {
                                            ...settings.quickActions,
                                            contextMenuEnabled: e.target.checked,
                                        },
                                    })
                                }
                                className="rounded"
                            />
                        </label>
                        <label className="flex items-center justify-between cursor-pointer">
                            <span className="text-sm">Auto-detect token addresses</span>
                            <input
                                type="checkbox"
                                checked={settings.quickActions.autoDetectAddresses}
                                onChange={(e) =>
                                    updateSettings({
                                        quickActions: {
                                            ...settings.quickActions,
                                            autoDetectAddresses: e.target.checked,
                                        },
                                    })
                                }
                                className="rounded"
                            />
                        </label>
                    </div>
                </div>
            </div>

            {/* Footer - Save Button */}
            <div className="border-t p-3">
                <Button
                    variant="default"
                    className="w-full"
                    onClick={handleSave}
                    disabled={!hasChanges}
                >
                    <Save className="h-4 w-4 mr-2" />
                    {hasChanges ? "Save Changes" : "No Changes"}
                </Button>
            </div>
        </div>
    );
}

