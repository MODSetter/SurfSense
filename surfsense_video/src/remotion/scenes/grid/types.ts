import { z } from "zod";

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

export const ListItem = z.object({
  category: z.literal("list"),
  title: z.string(),
  subtitle: z.string().optional(),
  bullets: z.array(z.string()),
  color: z.string(),
});

export const QuoteItem = z.object({
  category: z.literal("quote"),
  quote: z.string(),
  author: z.string(),
  role: z.string().optional(),
  color: z.string(),
});

export const ComparisonItem = z.object({
  category: z.literal("comparison"),
  title: z.string(),
  labelA: z.string(),
  valueA: z.string(),
  labelB: z.string(),
  valueB: z.string(),
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

export const RankingItem = z.object({
  category: z.literal("ranking"),
  rank: z.number(),
  title: z.string(),
  value: z.string().optional(),
  desc: z.string().optional(),
  color: z.string(),
});

export const KeyValueItem = z.object({
  category: z.literal("keyvalue"),
  title: z.string(),
  pairs: z.array(z.object({ label: z.string(), value: z.string() })),
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

export const StepItem = z.object({
  category: z.literal("step"),
  step: z.number(),
  title: z.string(),
  desc: z.string().optional(),
  color: z.string(),
});

export const DefinitionItem = z.object({
  category: z.literal("definition"),
  term: z.string(),
  definition: z.string(),
  example: z.string().optional(),
  color: z.string(),
});

export const CardItem = z.discriminatedUnion("category", [
  StatItem,
  InfoItem,
  ListItem,
  QuoteItem,
  ComparisonItem,
  ProfileItem,
  RankingItem,
  KeyValueItem,
  ProgressItem,
  FactItem,
  StepItem,
  DefinitionItem,
]);

export const GridSceneInput = z.object({
  type: z.literal("grid"),
  items: z.array(CardItem).min(1).max(8),
});

export type StatItem = z.infer<typeof StatItem>;
export type InfoItem = z.infer<typeof InfoItem>;
export type ListItem = z.infer<typeof ListItem>;
export type QuoteItem = z.infer<typeof QuoteItem>;
export type ComparisonItem = z.infer<typeof ComparisonItem>;
export type ProfileItem = z.infer<typeof ProfileItem>;
export type RankingItem = z.infer<typeof RankingItem>;
export type KeyValueItem = z.infer<typeof KeyValueItem>;
export type ProgressItem = z.infer<typeof ProgressItem>;
export type FactItem = z.infer<typeof FactItem>;
export type StepItem = z.infer<typeof StepItem>;
export type DefinitionItem = z.infer<typeof DefinitionItem>;
export type CardItem = z.infer<typeof CardItem>;
export type CardCategory = CardItem["category"];
export type GridSceneInput = z.infer<typeof GridSceneInput>;
