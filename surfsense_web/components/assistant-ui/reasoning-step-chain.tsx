"use client";
import React from "react";
import {
  ChainOfThought,
  ChainOfThoughtStep,
  ChainOfThoughtTrigger,
  ChainOfThoughtContent,
} from "../ui/chain-of-thought";
import type { ReasoningGroupProps } from "@assistant-ui/react";

/**
 * Groups steps (tool calls + reasoning) as a chain-of-thought.
 * Usage: Use as ReasoningGroup renderer for MessagePrimitive.Parts
 */
export function ReasoningStepChain({ startIndex, endIndex, children }: ReasoningGroupProps) {
  const steps = React.Children.toArray(children);
  return (
    <ChainOfThought>
      {steps.map((step, idx) => (
        <ChainOfThoughtStep key={idx} isLast={idx === steps.length - 1}>
          <ChainOfThoughtTrigger>
            {getSummary(step)}
          </ChainOfThoughtTrigger>
          <ChainOfThoughtContent>
            {step}
          </ChainOfThoughtContent>
        </ChainOfThoughtStep>
      ))}
    </ChainOfThought>
  );
}

function getSummary(step: React.ReactNode) {
  if (
    React.isValidElement(step) &&
    typeof step.props?.text === "string"
  ) {
    const text = step.props.text;
    const summary = text.split(/[.!?\n]/)[0].slice(0, 60);
    return summary;
  }
  return "Step";
}
