"use client";

import type { FC } from "react";
import { Button } from "@/components/ui/button";
import type { Action, ActionsConfig } from "./schema";

interface ActionButtonsProps {
  actions?: Action[] | ActionsConfig;
  onAction?: (actionId: string) => void;
  disabled?: boolean;
}

export const ActionButtons: FC<ActionButtonsProps> = ({ actions, onAction, disabled }) => {
  if (!actions) return null;

  // Normalize actions to array format
  const actionArray: Action[] = Array.isArray(actions)
    ? actions
    : [
        actions.confirm && { ...actions.confirm, id: "confirm" },
        actions.cancel && { ...actions.cancel, id: "cancel" },
      ].filter(Boolean) as Action[];

  if (actionArray.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 pt-3">
      {actionArray.map((action) => (
        <Button
          key={action.id}
          variant={action.variant || "default"}
          size="sm"
          disabled={disabled || action.disabled}
          onClick={() => onAction?.(action.id)}
        >
          {action.label}
        </Button>
      ))}
    </div>
  );
};

