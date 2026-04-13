import { useState } from "react";
import { cn } from "~/lib/utils";
import {
    Minus,
    ArrowRight,
    Type,
    Circle,
    Square,
    TrendingUp,
    Eraser,
    Undo,
    Redo,
} from "lucide-react";
import { Button } from "@/routes/ui/button";

export type AnnotationType = "line" | "arrow" | "text" | "circle" | "rectangle" | "fibonacci";

export interface Annotation {
    id: string;
    type: AnnotationType;
    coordinates: { x: number; y: number }[];
    text?: string;
    color: string;
}

export interface AnnotationToolsProps {
    /** Callback when annotation is added */
    onAnnotationAdd?: (annotation: Annotation) => void;
    /** Callback when annotation is removed */
    onAnnotationRemove?: (id: string) => void;
    /** Callback when undo is clicked */
    onUndo?: () => void;
    /** Callback when redo is clicked */
    onRedo?: () => void;
    /** Additional class names */
    className?: string;
}

/**
 * AnnotationTools - Drawing tools for chart annotations
 *
 * Features:
 * - Line tool for trend lines, support/resistance
 * - Arrow tool for directional indicators
 * - Text tool for labels
 * - Shape tools (circle, rectangle)
 * - Fibonacci retracement tool
 * - Color picker
 * - Undo/Redo functionality
 */
export function AnnotationTools({
    onAnnotationAdd,
    onAnnotationRemove,
    onUndo,
    onRedo,
    className,
}: AnnotationToolsProps) {
    const [selectedTool, setSelectedTool] = useState<AnnotationType | null>(null);
    const [selectedColor, setSelectedColor] = useState("#3b82f6"); // blue-500

    const tools: { type: AnnotationType; icon: any; label: string }[] = [
        { type: "line", icon: Minus, label: "Line" },
        { type: "arrow", icon: ArrowRight, label: "Arrow" },
        { type: "text", icon: Type, label: "Text" },
        { type: "circle", icon: Circle, label: "Circle" },
        { type: "rectangle", icon: Square, label: "Rectangle" },
        { type: "fibonacci", icon: TrendingUp, label: "Fibonacci" },
    ];

    const colors = [
        { value: "#3b82f6", label: "Blue" },
        { value: "#ef4444", label: "Red" },
        { value: "#22c55e", label: "Green" },
        { value: "#eab308", label: "Yellow" },
        { value: "#a855f7", label: "Purple" },
        { value: "#ffffff", label: "White" },
    ];

    const handleToolSelect = (tool: AnnotationType) => {
        setSelectedTool(tool === selectedTool ? null : tool);
    };

    return (
        <div className={cn("space-y-3", className)}>
            {/* Drawing Tools */}
            <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground">Drawing Tools</h4>
                <div className="grid grid-cols-3 gap-2">
                    {tools.map(({ type, icon: Icon, label }) => (
                        <button
                            key={type}
                            className={cn(
                                "flex flex-col items-center gap-1 p-2 rounded border transition-colors",
                                selectedTool === type
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-muted hover:bg-muted/80"
                            )}
                            onClick={() => handleToolSelect(type)}
                        >
                            <Icon className="h-4 w-4" />
                            <span className="text-xs">{label}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Color Picker */}
            <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground">Color</h4>
                <div className="flex gap-2">
                    {colors.map(({ value, label }) => (
                        <button
                            key={value}
                            className={cn(
                                "w-8 h-8 rounded-full border-2 transition-all",
                                selectedColor === value
                                    ? "border-primary scale-110"
                                    : "border-muted hover:scale-105"
                            )}
                            style={{ backgroundColor: value }}
                            onClick={() => setSelectedColor(value)}
                            title={label}
                        />
                    ))}
                </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={onUndo}
                >
                    <Undo className="h-3 w-3 mr-1" />
                    Undo
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={onRedo}
                >
                    <Redo className="h-3 w-3 mr-1" />
                    Redo
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedTool(null)}
                >
                    <Eraser className="h-3 w-3" />
                </Button>
            </div>

            {/* Instructions */}
            {selectedTool && (
                <div className="p-2 bg-muted/50 rounded text-xs text-muted-foreground">
                    {selectedTool === "line" && "Click and drag to draw a line"}
                    {selectedTool === "arrow" && "Click and drag to draw an arrow"}
                    {selectedTool === "text" && "Click to add text label"}
                    {selectedTool === "circle" && "Click and drag to draw a circle"}
                    {selectedTool === "rectangle" && "Click and drag to draw a rectangle"}
                    {selectedTool === "fibonacci" && "Click two points to draw Fibonacci retracement"}
                </div>
            )}
        </div>
    );
}

