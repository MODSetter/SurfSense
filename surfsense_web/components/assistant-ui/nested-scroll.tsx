"use client";

import { forwardRef, type ComponentPropsWithoutRef, type WheelEvent } from "react";

export type NestedScrollProps = ComponentPropsWithoutRef<"div">;

export const NestedScroll = forwardRef<HTMLDivElement, NestedScrollProps>(
	({ onWheel, ...props }, ref) => {
		const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
			const el = event.currentTarget;
			const canScrollUp = el.scrollTop > 0;
			const canScrollDown = el.scrollTop < el.scrollHeight - el.clientHeight - 1;
			const goingUp = event.deltaY < 0;
			const goingDown = event.deltaY > 0;
			if ((goingUp && canScrollUp) || (goingDown && canScrollDown)) {
				event.stopPropagation();
			}
			onWheel?.(event);
		};
		return <div ref={ref} onWheel={handleWheel} {...props} />;
	}
);

NestedScroll.displayName = "NestedScroll";
