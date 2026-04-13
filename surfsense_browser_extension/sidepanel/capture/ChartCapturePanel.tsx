import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    Camera,
    Download,
    Copy,
    Twitter,
    MessageSquare,
    Image as ImageIcon,
    Palette,
    Settings,
} from "lucide-react";
import { Button } from "@/routes/ui/button";
import { AnnotationTools } from "./AnnotationTools";

export interface ChartCaptureMetadata {
    tokenSymbol: string;
    tokenName: string;
    price: number;
    change24h: number;
    volume: number;
    liquidity: number;
    timestamp: Date;
}

export interface ChartCaptureSettings {
    style: "dark" | "light" | "neon";
    includeTokenInfo: boolean;
    includePriceChange: boolean;
    includeVolumeLiquidity: boolean;
    includeTimestamp: boolean;
    includeWatermark: boolean;
}

export interface ChartCapturePanelProps {
    /** Current token metadata */
    metadata?: ChartCaptureMetadata;
    /** Callback when capture is clicked */
    onCapture?: () => void;
    /** Callback when export is clicked */
    onExport?: (format: "twitter" | "telegram" | "instagram" | "clipboard") => void;
    /** Additional class names */
    className?: string;
}

/**
 * ChartCapturePanel - Chart screenshot tool with annotations
 *
 * Features:
 * - One-click chart capture from DexScreener
 * - Auto-add metadata overlay (token info, price, volume, etc.)
 * - Drawing tools (lines, arrows, text, shapes, Fibonacci)
 * - Template styles (dark, light, neon)
 * - Export options (Twitter, Telegram, Instagram, clipboard)
 */
export function ChartCapturePanel({
    metadata,
    onCapture,
    onExport,
    className,
}: ChartCapturePanelProps) {
    const [settings, setSettings] = useState<ChartCaptureSettings>({
        style: "dark",
        includeTokenInfo: true,
        includePriceChange: true,
        includeVolumeLiquidity: true,
        includeTimestamp: true,
        includeWatermark: false,
    });

    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [isCapturing, setIsCapturing] = useState(false);

    const handleCapture = async () => {
        setIsCapturing(true);
        await onCapture?.();
        // Mock: simulate capture
        setTimeout(() => {
            setCapturedImage("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==");
            setIsCapturing(false);
        }, 1000);
    };

    const handleExport = (format: "twitter" | "telegram" | "instagram" | "clipboard") => {
        onExport?.(format);
    };

    const formatCurrency = (value: number) => {
        if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
        if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
        return `$${value.toFixed(2)}`;
    };

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
                <div className="flex items-center gap-2">
                    <Camera className="h-5 w-5 text-primary" />
                    <div>
                        <h2 className="font-semibold">Chart Capture</h2>
                        {metadata && (
                            <p className="text-xs text-muted-foreground">
                                {metadata.tokenSymbol}
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Capture Button */}
                {!capturedImage && (
                    <Button
                        variant="default"
                        className="w-full"
                        onClick={handleCapture}
                        disabled={isCapturing}
                    >
                        <Camera className="h-4 w-4 mr-2" />
                        {isCapturing ? "Capturing..." : "Capture Chart"}
                    </Button>
                )}

                {/* Preview */}
                {capturedImage && (
                    <div className="space-y-3">
                        <div className="relative border rounded-lg overflow-hidden bg-muted/50">
                            <img
                                src={capturedImage}
                                alt="Captured chart"
                                className="w-full h-auto"
                            />
                            {/* Metadata Overlay Preview */}
                            {metadata && settings.includeTokenInfo && (
                                <div className="absolute top-2 left-2 bg-background/90 backdrop-blur-sm p-2 rounded text-xs">
                                    <div className="font-bold">{metadata.tokenSymbol}</div>
                                    {settings.includePriceChange && (
                                        <div className={cn(
                                            "font-semibold",
                                            metadata.change24h >= 0 ? "text-green-600" : "text-red-600"
                                        )}>
                                            ${metadata.price.toFixed(6)} ({metadata.change24h >= 0 ? "+" : ""}{metadata.change24h.toFixed(2)}%)
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Annotation Tools */}
                        <AnnotationTools />

                        {/* Recapture Button */}
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => setCapturedImage(null)}
                        >
                            <Camera className="h-4 w-4 mr-2" />
                            Recapture
                        </Button>
                    </div>
                )}

                {/* Style Selection */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Palette className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Style</h3>
                    </div>
                    <div className="flex gap-2">
                        {(["dark", "light", "neon"] as const).map((style) => (
                            <button
                                key={style}
                                className={cn(
                                    "flex-1 p-2 rounded border text-xs font-medium transition-colors",
                                    settings.style === style
                                        ? "bg-primary text-primary-foreground border-primary"
                                        : "bg-muted hover:bg-muted/80"
                                )}
                                onClick={() => setSettings({ ...settings, style })}
                            >
                                {style.charAt(0).toUpperCase() + style.slice(1)}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Metadata Options */}
                <div className="space-y-2">
                    <div className="flex items-center gap-2">
                        <Settings className="h-4 w-4 text-muted-foreground" />
                        <h3 className="font-semibold text-sm">Metadata</h3>
                    </div>
                    <div className="space-y-2">
                        {[
                            { key: "includeTokenInfo" as const, label: "Token info" },
                            { key: "includePriceChange" as const, label: "Price & change" },
                            { key: "includeVolumeLiquidity" as const, label: "Volume & liquidity" },
                            { key: "includeTimestamp" as const, label: "Timestamp" },
                            { key: "includeWatermark" as const, label: "Watermark" },
                        ].map(({ key, label }) => (
                            <label key={key} className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings[key]}
                                    onChange={(e) =>
                                        setSettings({ ...settings, [key]: e.target.checked })
                                    }
                                    className="rounded"
                                />
                                <span className="text-sm">{label}</span>
                            </label>
                        ))}
                    </div>
                </div>
            </div>

            {/* Footer - Export Options */}
            {capturedImage && (
                <div className="border-t p-3 space-y-2">
                    <h3 className="font-semibold text-xs text-muted-foreground mb-2">Export</h3>
                    <div className="grid grid-cols-2 gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleExport("twitter")}
                        >
                            <Twitter className="h-3 w-3 mr-1" />
                            Twitter
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleExport("telegram")}
                        >
                            <MessageSquare className="h-3 w-3 mr-1" />
                            Telegram
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleExport("instagram")}
                        >
                            <ImageIcon className="h-3 w-3 mr-1" />
                            Instagram
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleExport("clipboard")}
                        >
                            <Copy className="h-3 w-3 mr-1" />
                            Copy
                        </Button>
                    </div>
                    <Button
                        variant="default"
                        className="w-full"
                        onClick={() => handleExport("clipboard")}
                    >
                        <Download className="h-4 w-4 mr-2" />
                        Save to File
                    </Button>
                </div>
            )}
        </div>
    );
}

