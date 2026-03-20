import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

export interface ExtraField {
	label: string;
	key: string;
	value: string;
	type: "text" | "email" | "emails" | "datetime-local" | "textarea";
}

interface HitlEditPanelState {
	isOpen: boolean;
	title: string;
	content: string;
	toolName: string;
	extraFields?: ExtraField[];
	onSave: ((title: string, content: string, extraFieldValues?: Record<string, string>) => void) | null;
}

const initialState: HitlEditPanelState = {
	isOpen: false,
	title: "",
	content: "",
	toolName: "",
	extraFields: undefined,
	onSave: null,
};

export const hitlEditPanelAtom = atom<HitlEditPanelState>(initialState);

const preHitlCollapsedAtom = atom<boolean | null>(null);

export const openHitlEditPanelAtom = atom(
	null,
	(
		get,
		set,
		payload: {
			title: string;
			content: string;
			toolName: string;
			extraFields?: ExtraField[];
			onSave: (title: string, content: string, extraFieldValues?: Record<string, string>) => void;
		}
	) => {
		if (!get(hitlEditPanelAtom).isOpen) {
			set(preHitlCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		set(hitlEditPanelAtom, {
			isOpen: true,
			title: payload.title,
			content: payload.content,
			toolName: payload.toolName,
			extraFields: payload.extraFields,
			onSave: payload.onSave,
		});
		set(rightPanelTabAtom, "hitl-edit");
		set(rightPanelCollapsedAtom, false);
	}
);

export const closeHitlEditPanelAtom = atom(null, (get, set) => {
	set(hitlEditPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preHitlCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preHitlCollapsedAtom, null);
	}
});
