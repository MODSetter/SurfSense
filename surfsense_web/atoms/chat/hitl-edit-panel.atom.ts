import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface HitlEditPanelState {
	isOpen: boolean;
	title: string;
	content: string;
	toolName: string;
	onSave: ((title: string, content: string) => void) | null;
}

const initialState: HitlEditPanelState = {
	isOpen: false,
	title: "",
	content: "",
	toolName: "",
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
			onSave: (title: string, content: string) => void;
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
