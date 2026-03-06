import { useCallback, useRef } from "react";

const LONG_PRESS_DELAY = 500;

export function useLongPress(onLongPress: () => void, delay = LONG_PRESS_DELAY) {
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const triggeredRef = useRef(false);

	const start = useCallback(() => {
		triggeredRef.current = false;
		timerRef.current = setTimeout(() => {
			triggeredRef.current = true;
			onLongPress();
		}, delay);
	}, [onLongPress, delay]);

	const cancel = useCallback(() => {
		if (timerRef.current) {
			clearTimeout(timerRef.current);
			timerRef.current = null;
		}
	}, []);

	const handlers = {
		onTouchStart: start,
		onTouchEnd: cancel,
		onTouchMove: cancel,
	};

	const wasLongPress = useCallback(() => {
		if (triggeredRef.current) {
			triggeredRef.current = false;
			return true;
		}
		return false;
	}, []);

	return { handlers, wasLongPress };
}
