import { useState } from "react";
import { cn } from "~/lib/utils";
import { 
    ChevronDown, 
    ChevronRight, 
    Brain, 
    Search, 
    FileText, 
    Lightbulb,
    CheckCircle,
    Loader2
} from "lucide-react";

export type ThinkingStepType = "thinking" | "searching" | "reading" | "analyzing" | "complete";

export interface ThinkingStep {
    /** Step ID */
    id: string;
    /** Step type for icon selection */
    type: ThinkingStepType;
    /** Step title/label */
    title: string;
    /** Step description or content */
    content?: string;
    /** Whether step is currently active */
    isActive?: boolean;
    /** Whether step is complete */
    isComplete?: boolean;
    /** Timestamp */
    timestamp?: Date;
}

export interface ThinkingStepsDisplayProps {
    /** List of thinking steps */
    steps: ThinkingStep[];
    /** Whether AI is currently thinking */
    isThinking?: boolean;
    /** Whether to show expanded by default */
    defaultExpanded?: boolean;
    /** Additional class names */
    className?: string;
}

const STEP_ICONS: Record<ThinkingStepType, typeof Brain> = {
    thinking: Brain,
    searching: Search,
    reading: FileText,
    analyzing: Lightbulb,
    complete: CheckCircle,
};

const STEP_COLORS: Record<ThinkingStepType, string> = {
    thinking: "text-purple-500",
    searching: "text-blue-500",
    reading: "text-green-500",
    analyzing: "text-orange-500",
    complete: "text-green-600",
};

/**
 * ThinkingStepsDisplay - Shows AI reasoning process
 * 
 * Features:
 * - Collapsible thinking steps
 * - Step-specific icons and colors
 * - Active step animation
 * - Expandable step details
 */
export function ThinkingStepsDisplay({
    steps,
    isThinking = false,
    defaultExpanded = true,
    className,
}: ThinkingStepsDisplayProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    if (steps.length === 0 && !isThinking) {
        return null;
    }

    const activeStep = steps.find(s => s.isActive);
    const completedSteps = steps.filter(s => s.isComplete).length;

    return (
        <div className={cn("rounded-lg border bg-muted/30", className)}>
            {/* Header - clickable to expand/collapse */}
            <button
                className="w-full flex items-center gap-2 p-3 text-left hover:bg-muted/50 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                
                <Brain className={cn(
                    "h-4 w-4",
                    isThinking ? "text-purple-500 animate-pulse" : "text-muted-foreground"
                )} />
                
                <span className="flex-1 text-sm font-medium">
                    {isThinking ? "Thinking..." : "Thought Process"}
                </span>
                
                <span className="text-xs text-muted-foreground">
                    {completedSteps}/{steps.length} steps
                </span>
            </button>

            {/* Steps list */}
            {isExpanded && (
                <div className="px-3 pb-3 space-y-2">
                    {steps.map((step, index) => (
                        <StepItem key={step.id} step={step} index={index} />
                    ))}
                    
                    {/* Active thinking indicator */}
                    {isThinking && !activeStep && (
                        <div className="flex items-center gap-2 p-2 rounded-md bg-purple-500/10">
                            <Loader2 className="h-4 w-4 text-purple-500 animate-spin" />
                            <span className="text-sm text-purple-600 dark:text-purple-400">
                                Processing...
                            </span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/**
 * Individual step item
 */
function StepItem({ step, index }: { step: ThinkingStep; index: number }) {
    const [isDetailExpanded, setIsDetailExpanded] = useState(false);
    const Icon = STEP_ICONS[step.type];
    const colorClass = STEP_COLORS[step.type];

    return (
        <div
            className={cn(
                "rounded-md transition-colors",
                step.isActive && "bg-primary/5 ring-1 ring-primary/20",
                step.isComplete && "opacity-80"
            )}
        >
            <div 
                className="flex items-start gap-2 p-2 cursor-pointer"
                onClick={() => step.content && setIsDetailExpanded(!isDetailExpanded)}
            >
                {/* Step number or icon */}
                <div className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0",
                    step.isActive ? "bg-primary/10" : "bg-muted"
                )}>
                    {step.isActive ? (
                        <Loader2 className={cn("h-3 w-3 animate-spin", colorClass)} />
                    ) : step.isComplete ? (
                        <CheckCircle className="h-3 w-3 text-green-500" />
                    ) : (
                        <Icon className={cn("h-3 w-3", colorClass)} />
                    )}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                    <p className={cn(
                        "text-sm",
                        step.isActive && "font-medium"
                    )}>
                        {step.title}
                    </p>
                    
                    {/* Expandable detail */}
                    {step.content && isDetailExpanded && (
                        <p className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">
                            {step.content}
                        </p>
                    )}
                </div>

                {/* Expand indicator */}
                {step.content && (
                    <ChevronRight className={cn(
                        "h-4 w-4 text-muted-foreground transition-transform",
                        isDetailExpanded && "rotate-90"
                    )} />
                )}
            </div>
        </div>
    );
}
