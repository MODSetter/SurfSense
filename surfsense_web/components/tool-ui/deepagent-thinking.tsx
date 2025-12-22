"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Brain, CheckCircle2, Loader2, Search, Sparkles } from "lucide-react";
import { useMemo } from "react";
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtItem,
  ChainOfThoughtStep,
  ChainOfThoughtTrigger,
} from "@/components/prompt-kit/chain-of-thought";
import { cn } from "@/lib/utils";

/**
 * Types for the deepagent thinking/reasoning tool
 */
interface ThinkingStep {
  id: string;
  title: string;
  items: string[];
  status: "pending" | "in_progress" | "completed";
}

interface DeepAgentThinkingArgs {
  query?: string;
  context?: string;
}

interface DeepAgentThinkingResult {
  steps?: ThinkingStep[];
  status?: "thinking" | "searching" | "synthesizing" | "completed";
  summary?: string;
}

/**
 * Get icon based on step status and type
 */
function getStepIcon(status: "pending" | "in_progress" | "completed", title: string) {
  // Check for specific step types based on title keywords
  const titleLower = title.toLowerCase();
  
  if (status === "in_progress") {
    return <Loader2 className="size-4 animate-spin text-primary" />;
  }
  
  if (status === "completed") {
    return <CheckCircle2 className="size-4 text-emerald-500" />;
  }
  
  // Default icons based on step type
  if (titleLower.includes("search") || titleLower.includes("knowledge")) {
    return <Search className="size-4 text-muted-foreground" />;
  }
  
  if (titleLower.includes("analy") || titleLower.includes("understand")) {
    return <Brain className="size-4 text-muted-foreground" />;
  }
  
  return <Sparkles className="size-4 text-muted-foreground" />;
}

/**
 * Component to display a single thinking step
 */
function ThinkingStepDisplay({ step }: { step: ThinkingStep }) {
  const icon = useMemo(() => getStepIcon(step.status, step.title), [step.status, step.title]);
  
  return (
    <ChainOfThoughtStep defaultOpen={step.status === "in_progress"}>
      <ChainOfThoughtTrigger 
        leftIcon={icon}
        swapIconOnHover={step.status !== "in_progress"}
        className={cn(
          step.status === "in_progress" && "text-foreground font-medium",
          step.status === "completed" && "text-muted-foreground"
        )}
      >
        {step.title}
      </ChainOfThoughtTrigger>
      <ChainOfThoughtContent>
        {step.items.map((item, index) => (
          <ChainOfThoughtItem key={`${step.id}-item-${index}`}>
            {item}
          </ChainOfThoughtItem>
        ))}
      </ChainOfThoughtContent>
    </ChainOfThoughtStep>
  );
}

/**
 * Loading state with animated thinking indicator
 */
function ThinkingLoadingState({ status }: { status?: string }) {
  const statusText = useMemo(() => {
    switch (status) {
      case "searching":
        return "Searching knowledge base...";
      case "synthesizing":
        return "Synthesizing response...";
      case "thinking":
      default:
        return "Thinking...";
    }
  }, [status]);
  
  return (
    <div className="my-3 flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 px-4 py-3">
      <div className="relative">
        <Brain className="size-5 text-primary" />
        <span className="absolute -right-0.5 -top-0.5 flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
          <span className="relative inline-flex size-2 rounded-full bg-primary" />
        </span>
      </div>
      <span className="text-sm text-muted-foreground">{statusText}</span>
    </div>
  );
}

/**
 * DeepAgent Thinking Tool UI Component
 *
 * This component displays the agent's chain-of-thought reasoning
 * when the deepagent is processing a query. It shows thinking steps
 * in a collapsible, hierarchical format.
 */
export const DeepAgentThinkingToolUI = makeAssistantToolUI<
  DeepAgentThinkingArgs,
  DeepAgentThinkingResult
>({
  toolName: "deepagent_thinking",
  render: function DeepAgentThinkingUI({ args, result, status }) {
    // Loading state - tool is still running
    if (status.type === "running" || status.type === "requires-action") {
      return <ThinkingLoadingState status={result?.status} />;
    }

    // Incomplete/cancelled state
    if (status.type === "incomplete") {
      if (status.reason === "cancelled") {
        return null; // Don't show anything if cancelled
      }
      if (status.reason === "error") {
        return null; // Don't show error for thinking - it's not critical
      }
    }

    // No result or no steps - don't render anything
    if (!result?.steps || result.steps.length === 0) {
      return null;
    }

    // Render the chain of thought
    return (
      <div className="my-3 w-full">
        <ChainOfThought>
          {result.steps.map((step) => (
            <ThinkingStepDisplay key={step.id} step={step} />
          ))}
        </ChainOfThought>
      </div>
    );
  },
});

/**
 * Inline Thinking Display Component
 * 
 * A simpler version that can be used inline with the message content
 * for displaying reasoning without the full tool UI infrastructure.
 */
export function InlineThinkingDisplay({
  steps,
  isStreaming = false,
  className,
}: {
  steps: ThinkingStep[];
  isStreaming?: boolean;
  className?: string;
}) {
  if (steps.length === 0 && !isStreaming) {
    return null;
  }

  return (
    <div className={cn("my-3 w-full", className)}>
      {isStreaming && steps.length === 0 ? (
        <ThinkingLoadingState />
      ) : (
        <ChainOfThought>
          {steps.map((step) => (
            <ThinkingStepDisplay key={step.id} step={step} />
          ))}
        </ChainOfThought>
      )}
    </div>
  );
}

export type { ThinkingStep, DeepAgentThinkingArgs, DeepAgentThinkingResult };

