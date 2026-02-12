import { atom } from "jotai";

interface ReportPanelState {
	isOpen: boolean;
	reportId: number | null;
	title: string | null;
	wordCount: number | null;
	/** When set, uses public endpoints for fetching report data (public shared chat) */
	shareToken: string | null;
}

const initialState: ReportPanelState = {
	isOpen: false,
	reportId: null,
	title: null,
	wordCount: null,
	shareToken: null,
};

/** Core atom holding the report panel state */
export const reportPanelAtom = atom<ReportPanelState>(initialState);

/** Derived read-only atom for checking if panel is open */
export const reportPanelOpenAtom = atom((get) => get(reportPanelAtom).isOpen);

/** Action atom to open the report panel with a specific report */
export const openReportPanelAtom = atom(
	null,
	(
		_get,
		set,
		{
			reportId,
			title,
			wordCount,
			shareToken,
		}: { reportId: number; title: string; wordCount?: number; shareToken?: string | null }
	) => {
		set(reportPanelAtom, {
			isOpen: true,
			reportId,
			title,
			wordCount: wordCount ?? null,
			shareToken: shareToken ?? null,
		});
	}
);

/** Action atom to close the report panel */
export const closeReportPanelAtom = atom(null, (_, set) => {
	set(reportPanelAtom, initialState);
});
