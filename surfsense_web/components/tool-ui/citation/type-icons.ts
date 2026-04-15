import type { LucideIcon } from "lucide-react";
import { Code2, Database, File, FileText, Globe, Newspaper } from "lucide-react";
import type { CitationType } from "./schema";

export const TYPE_ICONS: Record<CitationType, LucideIcon> = {
	webpage: Globe,
	document: FileText,
	article: Newspaper,
	api: Database,
	code: Code2,
	other: File,
};
