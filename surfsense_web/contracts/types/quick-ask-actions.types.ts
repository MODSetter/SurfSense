export type QuickAskActionMode = "transform" | "explore";

export interface QuickAskAction {
	id: string;
	name: string;
	prompt: string;
	mode: QuickAskActionMode;
	icon: string;
	group: "transform" | "explore" | "knowledge" | "custom";
}
