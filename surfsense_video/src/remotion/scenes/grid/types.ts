/**
 * Zod schemas and inferred types for grid scene card data.
 * Each card category has its own schema; CardItem is the discriminated union.
 */
import { z } from "zod";

// ── Card category schemas ──

export const StatItem = z.object({
  category: z.literal("stat"),
  title: z.string(),
  value: z.string(),
  desc: z.string().optional(),
  color: z.string(),
});

export const InfoItem = z.object({
  category: z.literal("info"),
  title: z.string(),
  subtitle: z.string().optional(),
  desc: z.string(),
  tag: z.string().optional(),
  color: z.string(),
});

export const QuoteItem = z.object({
  category: z.literal("quote"),
  quote: z.string(),
  author: z.string(),
  role: z.string().optional(),
  color: z.string(),
});

export const ProfileItem = z.object({
  category: z.literal("profile"),
  name: z.string(),
  role: z.string(),
  desc: z.string().optional(),
  tag: z.string().optional(),
  color: z.string(),
});

export const ProgressItem = z.object({
  category: z.literal("progress"),
  title: z.string(),
  value: z.number(),
  max: z.number().optional(),
  desc: z.string().optional(),
  color: z.string(),
});

export const FactItem = z.object({
  category: z.literal("fact"),
  statement: z.string(),
  source: z.string().optional(),
  color: z.string(),
});

export const DefinitionItem = z.object({
  category: z.literal("definition"),
  term: z.string(),
  definition: z.string(),
  example: z.string().optional(),
  color: z.string(),
});

// ── Unions & scene input ──

export const CardItem = z.discriminatedUnion("category", [
  StatItem, InfoItem, QuoteItem, ProfileItem,
  ProgressItem, FactItem, DefinitionItem,
]);

export const GridSceneInput = z.object({
  type: z.literal("grid"),
  items: z.array(CardItem).min(1).max(8),
});

// ── Inferred types ──

export type StatItem = z.infer<typeof StatItem>;
export type InfoItem = z.infer<typeof InfoItem>;
export type QuoteItem = z.infer<typeof QuoteItem>;
export type ProfileItem = z.infer<typeof ProfileItem>;
export type ProgressItem = z.infer<typeof ProgressItem>;
export type FactItem = z.infer<typeof FactItem>;
export type DefinitionItem = z.infer<typeof DefinitionItem>;
export type CardItem = z.infer<typeof CardItem>;
export type CardCategory = CardItem["category"];
export type GridSceneInput = z.infer<typeof GridSceneInput>;
