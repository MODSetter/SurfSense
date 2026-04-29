import { atom } from "jotai";

export type PremiumAlertState = {
	message: string;
};

export const premiumAlertByThreadAtom = atom<Record<number, PremiumAlertState>>({});

export const setPremiumAlertForThreadAtom = atom(
	null,
	(
		get,
		set,
		payload: {
			threadId: number;
			message: string;
			userId?: string | null;
		}
	) => {
		const storageKey = `surfsense-premium-alert-seen-v1:${payload.userId ?? "anonymous"}`;

		if (typeof window !== "undefined") {
			const hasSeen = localStorage.getItem(storageKey) === "true";
			if (hasSeen) return;
		}

		const current = get(premiumAlertByThreadAtom);
		set(premiumAlertByThreadAtom, {
			...current,
			[payload.threadId]: { message: payload.message },
		});

		if (typeof window !== "undefined") {
			localStorage.setItem(storageKey, "true");
		}
	}
);

export const clearPremiumAlertForThreadAtom = atom(null, (get, set, threadId: number) => {
	const current = get(premiumAlertByThreadAtom);
	if (!(threadId in current)) return;
	const next = { ...current };
	delete next[threadId];
	set(premiumAlertByThreadAtom, next);
});
