import { atom } from "jotai";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";

interface ReportPanelState {
	isOpen: boolean;
	reportId: number | null;
	title: string | null;
	wordCount: number | null;
	/** When set, uses public endpoints for fetching report data (public shared chat) */
	shareToken: string | null;
	/** Content type of the report — "markdown" (default) or "typst" (resume) */
	contentType: string;
}

const initialState: ReportPanelState = {
	isOpen: false,
	reportId: null,
	title: null,
	wordCount: null,
	shareToken: null,
	contentType: "markdown",
};

/** Core atom holding the report panel state */
export const reportPanelAtom = atom<ReportPanelState>(initialState);

/** Derived read-only atom for checking if panel is open */
export const reportPanelOpenAtom = atom((get) => get(reportPanelAtom).isOpen);

/** Snapshot of `rightPanelCollapsedAtom` taken before the report opens */
const preReportCollapsedAtom = atom<boolean | null>(null);

/** Action atom to open the report panel with a specific report */
export const openReportPanelAtom = atom(
	null,
	(
		get,
		set,
		{
			reportId,
			title,
			wordCount,
			shareToken,
			contentType,
		}: { reportId: number; title: string; wordCount?: number; shareToken?: string | null; contentType?: string }
	) => {
		if (!get(reportPanelAtom).isOpen) {
			set(preReportCollapsedAtom, get(rightPanelCollapsedAtom));
		}
		set(reportPanelAtom, {
			isOpen: true,
			reportId,
			title,
			wordCount: wordCount ?? null,
			shareToken: shareToken ?? null,
			contentType: contentType ?? "markdown",
		});
		set(rightPanelTabAtom, "report");
		set(rightPanelCollapsedAtom, false);
	}
);

/** Action atom to close the report panel */
export const closeReportPanelAtom = atom(null, (get, set) => {
	set(reportPanelAtom, initialState);
	set(rightPanelTabAtom, "sources");
	const prev = get(preReportCollapsedAtom);
	if (prev !== null) {
		set(rightPanelCollapsedAtom, prev);
		set(preReportCollapsedAtom, null);
	}
});
