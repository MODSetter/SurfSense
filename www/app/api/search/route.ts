import { createFromSource } from "fumadocs-core/search/server";
import { source } from "@/features/docs/source";

export const { GET } = createFromSource(source);
