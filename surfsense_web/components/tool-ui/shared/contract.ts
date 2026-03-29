import { z } from "zod";
import { parseWithSchema, safeParseWithSchema } from "./parse";

export interface ToolUiContract<T> {
  schema: z.ZodType<T>;
  parse: (input: unknown) => T;
  safeParse: (input: unknown) => T | null;
}

export function defineToolUiContract<T>(
  componentName: string,
  schema: z.ZodType<T>,
): ToolUiContract<T> {
  return {
    schema,
    parse: (input: unknown) => parseWithSchema(schema, input, componentName),
    safeParse: (input: unknown) => safeParseWithSchema(schema, input),
  };
}
