import { z } from "zod";

function formatZodPath(path: Array<string | number | symbol>): string {
  if (path.length === 0) return "root";
  return path
    .map((segment) =>
      typeof segment === "number" ? `[${segment}]` : String(segment),
    )
    .join(".");
}

/**
 * Format Zod errors into a compact `path: message` string.
 */
export function formatZodError(error: z.ZodError): string {
  const parts = error.issues.map((issue) => {
    const path = formatZodPath(issue.path);
    return `${path}: ${issue.message}`;
  });

  return Array.from(new Set(parts)).join("; ");
}

/**
 * Parse unknown input and throw a readable error.
 */
export function parseWithSchema<T>(
  schema: z.ZodType<T>,
  input: unknown,
  name: string,
): T {
  const res = schema.safeParse(input);
  if (!res.success) {
    throw new Error(`Invalid ${name} payload: ${formatZodError(res.error)}`);
  }
  return res.data;
}

/**
 * Parse unknown input, returning `null` instead of throwing on failure.
 *
 * Use this in assistant-ui `render` functions where `args` stream in
 * incrementally and may be incomplete until the tool call finishes.
 */
export function safeParseWithSchema<T>(
  schema: z.ZodType<T>,
  input: unknown,
): T | null {
  const res = schema.safeParse(input);
  return res.success ? res.data : null;
}
