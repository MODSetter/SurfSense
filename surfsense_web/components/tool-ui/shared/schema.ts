import { z } from "zod";
import type { ReactNode } from "react";

/**
 * Tool UI conventions:
 * - Serializable schemas are JSON-safe (no callbacks/ReactNode/`className`).
 * - Schema: `SerializableXSchema`
 * - Parser: `parseSerializableX(input: unknown)` (throws on invalid)
 * - Safe parser: `safeParseSerializableX(input: unknown)` (returns `null` on invalid)
 * - Actions: `LocalActions` for non-receipt actions and `DecisionActions` for consequential actions
 * - Root attrs: `data-tool-ui-id` + `data-slot`
 */

/**
 * Schema for tool UI identity.
 *
 * Every tool UI should have a unique identifier that:
 * - Is stable across re-renders
 * - Is meaningful (not auto-generated)
 * - Is unique within the conversation
 *
 * Format recommendation: `{component-type}-{semantic-identifier}`
 * Examples: "data-table-expenses-q3", "option-list-deploy-target"
 */
export const ToolUIIdSchema = z.string().min(1);

export type ToolUIId = z.infer<typeof ToolUIIdSchema>;

/**
 * Primary role of a Tool UI surface in a chat context.
 */
export const ToolUIRoleSchema = z.enum([
  "information",
  "decision",
  "control",
  "state",
  "composite",
]);

export type ToolUIRole = z.infer<typeof ToolUIRoleSchema>;

export const ToolUIReceiptOutcomeSchema = z.enum([
  "success",
  "partial",
  "failed",
  "cancelled",
]);

export type ToolUIReceiptOutcome = z.infer<typeof ToolUIReceiptOutcomeSchema>;

/**
 * Optional receipt metadata: a durable summary of an outcome.
 */
export const ToolUIReceiptSchema = z.object({
  outcome: ToolUIReceiptOutcomeSchema,
  summary: z.string().min(1),
  identifiers: z.record(z.string(), z.string()).optional(),
  at: z.string().datetime(),
});

export type ToolUIReceipt = z.infer<typeof ToolUIReceiptSchema>;

/**
 * Base schema for Tool UI payloads (id + optional role/receipt).
 */
export const ToolUISurfaceSchema = z.object({
  id: ToolUIIdSchema,
  role: ToolUIRoleSchema.optional(),
  receipt: ToolUIReceiptSchema.optional(),
});

export type ToolUISurface = z.infer<typeof ToolUISurfaceSchema>;

export const ActionSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  /**
   * Canonical narration the assistant can use after this action is taken.
   *
   * Example: "I exported the table as CSV." / "I opened the link in a new tab."
   */
  sentence: z.string().optional(),
  confirmLabel: z.string().optional(),
  variant: z
    .enum(["default", "destructive", "secondary", "ghost", "outline"])
    .optional(),
  icon: z.custom<ReactNode>().optional(),
  loading: z.boolean().optional(),
  disabled: z.boolean().optional(),
  shortcut: z.string().optional(),
});

export type Action = z.infer<typeof ActionSchema>;
export type LocalAction = Action;
export type DecisionAction = Action;

export const DecisionResultSchema = z.object({
  kind: z.literal("decision"),
  version: z.literal(1),
  decisionId: z.string().min(1),
  actionId: z.string().min(1),
  actionLabel: z.string().min(1),
  at: z.string().datetime(),
  payload: z.record(z.string(), z.unknown()).optional(),
});

export type DecisionResult<
  TPayload extends Record<string, unknown> = Record<string, unknown>,
> = Omit<z.infer<typeof DecisionResultSchema>, "payload"> & {
  payload?: TPayload;
};

export function createDecisionResult<
  TPayload extends Record<string, unknown> = Record<string, unknown>,
>(args: {
  decisionId: string;
  action: { id: string; label: string };
  payload?: TPayload;
}): DecisionResult<TPayload> {
  return {
    kind: "decision",
    version: 1,
    decisionId: args.decisionId,
    actionId: args.action.id,
    actionLabel: args.action.label,
    at: new Date().toISOString(),
    payload: args.payload,
  };
}

export const ActionButtonsPropsSchema = z.object({
  actions: z.array(ActionSchema).min(1),
  align: z.enum(["left", "center", "right"]).optional(),
  confirmTimeout: z.number().positive().optional(),
  className: z.string().optional(),
});

export const SerializableActionSchema = ActionSchema.omit({ icon: true });
export const SerializableActionsSchema = ActionButtonsPropsSchema.extend({
  actions: z.array(SerializableActionSchema),
}).omit({ className: true });

export interface ActionsConfig {
  items: Action[];
  align?: "left" | "center" | "right";
  confirmTimeout?: number;
}

export const SerializableActionsConfigSchema = z.object({
  items: z.array(SerializableActionSchema).min(1),
  align: z.enum(["left", "center", "right"]).optional(),
  confirmTimeout: z.number().positive().optional(),
});

export type SerializableActionsConfig = z.infer<
  typeof SerializableActionsConfigSchema
>;

export type SerializableAction = z.infer<typeof SerializableActionSchema>;
