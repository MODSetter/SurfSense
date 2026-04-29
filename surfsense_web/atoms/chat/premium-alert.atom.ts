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
		}
	) => {
		const current = get(premiumAlertByThreadAtom);
		set(premiumAlertByThreadAtom, {
			...current,
			[payload.threadId]: { message: payload.message },
		});
	}
);

export const clearPremiumAlertForThreadAtom = atom(null, (get, set, threadId: number) => {
	const current = get(premiumAlertByThreadAtom);
	if (!(threadId in current)) return;
	const next = { ...current };
	delete next[threadId];
	set(premiumAlertByThreadAtom, next);
});
