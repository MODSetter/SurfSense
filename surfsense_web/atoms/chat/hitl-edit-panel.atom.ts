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
	contentFormat?: "markdown" | "html";
	extraFields?: ExtraField[];
	onSave:
		| ((title: string, content: string, extraFieldValues?: Record<string, string>) => void)
		| null;
	onClose: (() => void) | null;
}

const initialState: HitlEditPanelState = {
	isOpen: false,
	title: "",
	content: "",
	toolName: "",
	contentFormat: undefined,
	extraFields: undefined,
	onSave: null,
	onClose: null,
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
			contentFormat?: "markdown" | "html";
			extraFields?: ExtraField[];
			onSave: (title: string, content: string, extraFieldValues?: Record<string, string>) => void;
			onClose?: () => void;
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
			contentFormat: payload.contentFormat,
			extraFields: payload.extraFields,
			onSave: payload.onSave,
			onClose: payload.onClose ?? null,
		});
		set(rightPanelTabAtom, "hitl-edit");
		set(rightPanelCollapsedAtom, false);
	}
);

export const closeHitlEditPanelAtom = atom(null, (get, set) => {
	const current = get(hitlEditPanelAtom);
	current.onClose?.();
	set(hitlEditPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preHitlCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preHitlCollapsedAtom, null);
	}
});
