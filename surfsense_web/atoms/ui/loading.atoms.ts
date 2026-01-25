import { atom } from "jotai";

interface GlobalLoadingState {
	isLoading: boolean;
	message?: string;
	variant: "login" | "default";
}

export const globalLoadingAtom = atom<GlobalLoadingState>({
	isLoading: false,
	message: undefined,
	variant: "default",
});

// Helper atom for showing global loading
export const showGlobalLoadingAtom = atom(
	null,
	(
		get,
		set,
		{ message, variant = "default" }: { message?: string; variant?: "login" | "default" }
	) => {
		set(globalLoadingAtom, { isLoading: true, message, variant });
	}
);

// Helper atom for hiding global loading
export const hideGlobalLoadingAtom = atom(null, (get, set) => {
	set(globalLoadingAtom, { isLoading: false, message: undefined, variant: "default" });
});
