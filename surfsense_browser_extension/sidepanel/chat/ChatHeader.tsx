import { useState } from "react";
import {
    Settings,
    ChevronDown,
    User,
    LogOut,
    ExternalLink,
    Star,
    Bell,
    MessageSquare,
    Plug,
    Search,
    X
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { cn } from "~/lib/utils";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/routes/ui/popover";

export interface SearchSpace {
    id: string;
    name: string;
    icon?: string;
}

export interface ChatHeaderProps {
    /** Available search spaces */
    searchSpaces?: SearchSpace[];
    /** Currently selected search space */
    selectedSpace?: SearchSpace;
    /** Callback when search space is changed */
    onSpaceChange?: (space: SearchSpace) => void;
    /** User display name */
    userName?: string;
    /** User avatar URL */
    userAvatar?: string;
    /** Callback when logout is clicked */
    onLogout?: () => void;
    /** Callback when settings item is clicked */
    onSettingsClick?: (item: string) => void;
    /** Callback when token search is triggered */
    onTokenSearch?: (query: string) => void;
}

/**
 * Enhanced Chat header with branding, token search, space selector, settings, and user menu
 *
 * Features:
 * - Universal token search bar (works on any page)
 * - Search space selector dropdown
 * - Settings dropdown with full menu
 * - User avatar with logout option
 */
export function ChatHeader({
    searchSpaces = [],
    selectedSpace,
    onSpaceChange,
    userName,
    userAvatar,
    onLogout,
    onSettingsClick,
    onTokenSearch,
}: ChatHeaderProps) {
    const [spaceOpen, setSpaceOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");

    const defaultSpaces: SearchSpace[] = [
        { id: "crypto", name: "Crypto", icon: "🪙" },
        { id: "general", name: "General", icon: "📚" },
        { id: "research", name: "Research", icon: "🔬" },
    ];

    const spaces = searchSpaces.length > 0 ? searchSpaces : defaultSpaces;
    const currentSpace = selectedSpace || spaces[0];

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (searchQuery.trim() && onTokenSearch) {
            onTokenSearch(searchQuery.trim());
        }
    };

    const handleClearSearch = () => {
        setSearchQuery("");
    };

    return (
        <div className="flex flex-col border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            {/* Top row: Logo, Space Selector, Settings */}
            <div className="flex items-center justify-between p-3 pb-2">
                {/* Logo and brand */}
                <div className="flex items-center gap-2">
                    <img
                        src="/assets/icon.png"
                        alt="SurfSense"
                        className="w-6 h-6"
                    />
                    <h1 className="font-semibold text-base">SurfSense</h1>
                </div>

                {/* Search Space Selector */}
                <Popover open={spaceOpen} onOpenChange={setSpaceOpen}>
                    <PopoverTrigger asChild>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 gap-1 px-2"
                        >
                            <span>{currentSpace.icon}</span>
                            <span className="max-w-[80px] truncate">{currentSpace.name}</span>
                            <ChevronDown className="h-3 w-3 opacity-50" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-48 p-1" align="center">
                        <div className="space-y-0.5">
                            {spaces.map((space) => (
                                <button
                                    key={space.id}
                                    className={cn(
                                        "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                                        currentSpace.id === space.id
                                            ? "bg-primary/10 text-primary"
                                            : "hover:bg-muted"
                                    )}
                                    onClick={() => {
                                        onSpaceChange?.(space);
                                        setSpaceOpen(false);
                                    }}
                                >
                                    <span>{space.icon}</span>
                                    <span>{space.name}</span>
                                </button>
                            ))}
                        </div>
                    </PopoverContent>
                </Popover>

                {/* Right side actions */}
                <div className="flex items-center gap-1">
                    {/* Settings Dropdown */}
                    <Popover open={settingsOpen} onOpenChange={setSettingsOpen}>
                        <PopoverTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                                <Settings className="h-4 w-4" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-56 p-1" align="end">
                            <SettingsMenu
                                onItemClick={(item) => {
                                    onSettingsClick?.(item);
                                    setSettingsOpen(false);
                                }}
                                onLogout={onLogout}
                            />
                        </PopoverContent>
                    </Popover>

                    {/* User Avatar */}
                    <UserAvatar
                        name={userName}
                        avatarUrl={userAvatar}
                        onLogout={onLogout}
                    />
                </div>
            </div>

            {/* Bottom row: Token Search Bar */}
            <div className="px-3 pb-2">
                <form onSubmit={handleSearch} className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    <input
                        type="text"
                        placeholder="Search token (symbol, name, or address)..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full h-8 pl-9 pr-8 text-sm rounded-md border border-input bg-background/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
                    />
                    {searchQuery && (
                        <button
                            type="button"
                            onClick={handleClearSearch}
                            className="absolute right-2 top-1/2 -translate-y-1/2 h-5 w-5 flex items-center justify-center rounded-sm hover:bg-muted transition-colors"
                        >
                            <X className="h-3 w-3 text-muted-foreground" />
                        </button>
                    )}
                </form>
            </div>
        </div>
    );
}

/**
 * Settings menu items
 */
function SettingsMenu({
    onItemClick,
    onLogout,
}: {
    onItemClick?: (item: string) => void;
    onLogout?: () => void;
}) {
    const menuItems = [
        { id: "connectors", label: "Manage Connectors", icon: Plug },
        { id: "chats", label: "View All Chats", icon: MessageSquare },
        { id: "watchlist", label: "Manage Watchlist", icon: Star },
        { id: "alerts", label: "Alert History", icon: Bell },
        { id: "settings", label: "Full Settings", icon: Settings, external: true },
    ];

    return (
        <div className="space-y-0.5">
            {menuItems.map((item) => (
                <button
                    key={item.id}
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors"
                    onClick={() => onItemClick?.(item.id)}
                >
                    <item.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {item.external && <ExternalLink className="h-3 w-3 opacity-50" />}
                </button>
            ))}

            <div className="my-1 border-t" />

            <button
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-destructive/10 text-destructive transition-colors"
                onClick={onLogout}
            >
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
            </button>
        </div>
    );
}

/**
 * User avatar component
 */
function UserAvatar({
    name,
    avatarUrl,
    onLogout,
}: {
    name?: string;
    avatarUrl?: string;
    onLogout?: () => void;
}) {
    const initials = name
        ? name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
        : "U";

    return (
        <Popover>
            <PopoverTrigger asChild>
                <button className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center overflow-hidden hover:ring-2 hover:ring-primary/20 transition-all">
                    {avatarUrl ? (
                        <img src={avatarUrl} alt={name || "User"} className="w-full h-full object-cover" />
                    ) : (
                        <span className="text-xs font-medium text-primary">{initials}</span>
                    )}
                </button>
            </PopoverTrigger>
            <PopoverContent className="w-48 p-2" align="end">
                <div className="text-center pb-2 border-b mb-2">
                    <p className="font-medium text-sm">{name || "User"}</p>
                </div>
                <button
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-destructive/10 text-destructive transition-colors"
                    onClick={onLogout}
                >
                    <LogOut className="h-4 w-4" />
                    <span>Logout</span>
                </button>
            </PopoverContent>
        </Popover>
    );
}
