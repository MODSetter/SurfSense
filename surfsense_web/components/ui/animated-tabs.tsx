"use client";

import React, {
	createContext,
	forwardRef,
	type ReactNode,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";

import { cn } from "@/lib/utils";

/* ───────────────────────────
   Context (replaces cloneElement)
   ─────────────────────────── */

interface TabsContextValue {
	activeValue: string;
	onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext() {
	const ctx = useContext(TabsContext);
	if (!ctx) {
		throw new Error("AnimatedTabs compound components must be rendered inside <Tabs>");
	}
	return ctx;
}

/* ───────────────────────────
   Constants (hoisted out of render)
   ─────────────────────────── */

const SIZE_CLASSES = {
	sm: "h-[32px] text-sm",
	md: "h-[40px] text-base",
	lg: "h-[48px] text-lg",
} as const;

const VARIANT_CLASSES = {
	default: "",
	pills: "rounded-full",
	underlined: "",
} as const;

const ACTIVE_INDICATOR_CLASSES = {
	default: "h-[2px] bg-primary dark:bg-primary",
	pills: "hidden",
	underlined: "h-[2px] bg-primary dark:bg-primary",
} as const;

const HOVER_INDICATOR_CLASSES = {
	default: "bg-muted dark:bg-muted rounded-[6px]",
	pills: "bg-muted dark:bg-muted rounded-full",
	underlined: "bg-muted dark:bg-muted rounded-[6px]",
} as const;

/* ───────────────────────────
   XScrollable (internal)
   ─────────────────────────── */

const XScrollable = forwardRef<
	HTMLDivElement,
	{
		className?: string;
		children?: ReactNode;
		showScrollbar?: boolean;
		contentClassName?: string;
	} & React.HTMLAttributes<HTMLDivElement>
>(({ className, children, showScrollbar = true, contentClassName, ...props }, ref) => {
	const scrollRef = useRef<HTMLDivElement | null>(null);
	const dragging = useRef(false);
	const startX = useRef(0);
	const startScrollLeft = useRef(0);
	const [scrollPos, setScrollPos] = useState<"start" | "middle" | "end" | "none">("none");

	const updateScrollPos = useCallback(() => {
		const el = scrollRef.current;
		if (!el) return;
		const canScroll = el.scrollWidth > el.clientWidth + 1;
		if (!canScroll) {
			setScrollPos("none");
			return;
		}
		const atStart = el.scrollLeft <= 2;
		const atEnd = el.scrollWidth - el.scrollLeft - el.clientWidth <= 2;
		setScrollPos(atStart ? "start" : atEnd ? "end" : "middle");
	}, []);

	useEffect(() => {
		updateScrollPos();
		const el = scrollRef.current;
		if (!el) return;
		const ro = new ResizeObserver(updateScrollPos);
		ro.observe(el);
		return () => ro.disconnect();
	}, [updateScrollPos]);

	const onMouseDown = (e: React.MouseEvent) => {
		if (!scrollRef.current) return;
		dragging.current = true;
		startX.current = e.clientX;
		startScrollLeft.current = scrollRef.current.scrollLeft;
	};
	const endDrag = () => {
		dragging.current = false;
	};
	const onMouseMove = (e: React.MouseEvent) => {
		if (!dragging.current || !scrollRef.current) return;
		e.preventDefault();
		const dx = e.clientX - startX.current;
		scrollRef.current.scrollLeft = startScrollLeft.current - dx;
	};

	const onWheel = (e: React.WheelEvent) => {
		if (!scrollRef.current) return;
		const delta = Math.abs(e.deltaY) > Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
		if (delta !== 0) {
			e.preventDefault();
			scrollRef.current.scrollLeft += delta;
		}
	};

	const handleScroll = useCallback(() => {
		updateScrollPos();
	}, [updateScrollPos]);

	const needsMask = scrollPos !== "none";
	const maskStart = scrollPos === "start" || scrollPos === "none" ? "black" : "transparent";
	const maskEnd = scrollPos === "end" || scrollPos === "none" ? "black" : "transparent";
	const maskImage = needsMask
		? `linear-gradient(to right, ${maskStart}, black 24px, black calc(100% - 24px), ${maskEnd})`
		: undefined;

	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: drag-scroll container needs mouse events
		<div
			ref={ref}
			className={cn("relative", className)}
			{...props}
			onMouseLeave={endDrag}
			onMouseUp={endDrag}
			onMouseMove={onMouseMove}
		>
			{/* biome-ignore lint/a11y/noStaticElementInteractions: drag-scroll requires onMouseDown */}
			<div
				ref={scrollRef}
				className={cn(
					"overflow-x-auto overflow-y-hidden whitespace-nowrap [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden",
					!showScrollbar && "scrollbar-none",
					contentClassName
				)}
				style={{
					maskImage,
					WebkitMaskImage: maskImage,
				}}
				onWheel={onWheel}
				onMouseDown={onMouseDown}
				onScroll={handleScroll}
			>
				{children}
			</div>
		</div>
	);
});
XScrollable.displayName = "XScrollable";

/* ───────────────────────────
   Tabs (root)
   ─────────────────────────── */

const Tabs = forwardRef<
	HTMLDivElement,
	{
		defaultValue?: string;
		value?: string;
		onValueChange?: (value: string) => void;
		className?: string;
		children?: ReactNode;
	}
>(({ defaultValue, value, onValueChange, className, children, ...props }, ref) => {
	const [activeValue, setActiveValue] = useState(value || defaultValue || "");

	useEffect(() => {
		if (value !== undefined) {
			setActiveValue(value);
		}
	}, [value]);

	const handleValueChange = useCallback(
		(newValue: string) => {
			if (value === undefined) {
				setActiveValue(newValue);
			}
			onValueChange?.(newValue);
		},
		[onValueChange, value]
	);
	const contextValue = useMemo(
		() => ({ activeValue, onValueChange: handleValueChange }),
		[activeValue, handleValueChange]
	);
	return (
		<TabsContext.Provider value={contextValue}>
			<div ref={ref} className={cn("tabs-container", className)} {...props}>
				{children}
			</div>
		</TabsContext.Provider>
	);
});
Tabs.displayName = "Tabs";

/* ───────────────────────────
   TabsList
   ─────────────────────────── */

type TabsListVariant = "default" | "pills" | "underlined";
type TabsListSize = "sm" | "md" | "lg";

const TabsList = forwardRef<
	HTMLDivElement,
	{
		className?: string;
		children?: ReactNode;
		showHoverEffect?: boolean;
		showActiveIndicator?: boolean;
		activeIndicatorPosition?: "top" | "bottom";
		activeIndicatorOffset?: number;
		size?: TabsListSize;
		variant?: TabsListVariant;
		stretch?: boolean;
		ariaLabel?: string;
		showBottomBorder?: boolean;
		bottomBorderClassName?: string;
		activeIndicatorClassName?: string;
		hoverIndicatorClassName?: string;
	}
>(
	(
		{
			className,
			children,
			showHoverEffect = true,
			showActiveIndicator = true,
			activeIndicatorPosition = "bottom",
			activeIndicatorOffset = 0,
			size = "sm",
			variant = "default",
			stretch = false,
			ariaLabel = "Tabs",
			showBottomBorder = false,
			bottomBorderClassName,
			activeIndicatorClassName,
			hoverIndicatorClassName,
			...props
		},
		ref
	) => {
		const { activeValue, onValueChange } = useTabsContext();

		const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
		const [hoverStyle, setHoverStyle] = useState({});
		const [activeStyle, setActiveStyle] = useState({
			left: "0px",
			width: "0px",
		});
		const tabRefs = useRef<(HTMLDivElement | null)[]>([]);
		const scrollContainerRef = useRef<HTMLDivElement | null>(null);

		const activeIndex = React.Children.toArray(children).findIndex(
			(child) =>
				React.isValidElement(child) &&
				(child as React.ReactElement<{ value: string }>).props.value === activeValue
		);

		useEffect(() => {
			if (hoveredIndex !== null && showHoverEffect) {
				const hoveredElement = tabRefs.current[hoveredIndex];
				if (hoveredElement) {
					const { offsetLeft, offsetWidth } = hoveredElement;
					setHoverStyle({
						left: `${offsetLeft}px`,
						width: `${offsetWidth}px`,
					});
				}
			}
		}, [hoveredIndex, showHoverEffect]);

		const updateActiveIndicator = useCallback(() => {
			if (showActiveIndicator && activeIndex >= 0) {
				const activeElement = tabRefs.current[activeIndex];
				if (activeElement) {
					const { offsetLeft, offsetWidth } = activeElement;
					setActiveStyle({
						left: `${offsetLeft}px`,
						width: `${offsetWidth}px`,
					});
				}
			}
		}, [showActiveIndicator, activeIndex]);

		useEffect(() => {
			updateActiveIndicator();
		}, [updateActiveIndicator]);

		useEffect(() => {
			requestAnimationFrame(updateActiveIndicator);
		}, [updateActiveIndicator]);

		const scrollTabToCenter = useCallback((index: number) => {
			const tabElement = tabRefs.current[index];
			const scrollContainer = scrollContainerRef.current;

			if (tabElement && scrollContainer) {
				const containerWidth = scrollContainer.offsetWidth;
				const tabWidth = tabElement.offsetWidth;
				const tabLeft = tabElement.offsetLeft;
				const scrollTarget = tabLeft - containerWidth / 2 + tabWidth / 2;
				scrollContainer.scrollTo({ left: scrollTarget, behavior: "smooth" });
			}
		}, []);

		const setTabRef = useCallback((el: HTMLDivElement | null, index: number) => {
			tabRefs.current[index] = el;
		}, []);

		const handleScrollableRef = useCallback((node: HTMLDivElement | null) => {
			if (node) {
				const scrollableDiv = node.querySelector('div[class*="overflow-x-auto"]');
				if (scrollableDiv) {
					scrollContainerRef.current = scrollableDiv as HTMLDivElement;
				}
			}
		}, []);

		useEffect(() => {
			if (activeIndex >= 0) {
				const timer = setTimeout(() => {
					scrollTabToCenter(activeIndex);
				}, 100);
				return () => clearTimeout(timer);
			}
		}, [activeIndex, scrollTabToCenter]);

		return (
			<div
				ref={handleScrollableRef}
				className={cn("relative", className)}
				role="tablist"
				aria-label={ariaLabel}
				{...props}
			>
				{showBottomBorder && (
					<div
						className={cn(
							"absolute bottom-0 left-0 right-0 h-px bg-border dark:bg-border z-0",
							bottomBorderClassName
						)}
					/>
				)}
				<XScrollable showScrollbar={false}>
					<div className={cn("relative", showBottomBorder && "pb-px")}>
						{showHoverEffect && (
							<div
								className={cn(
									"absolute transition-[left,width,opacity] duration-300 ease-out flex items-center z-0",
									SIZE_CLASSES[size],
									HOVER_INDICATOR_CLASSES[variant],
									hoverIndicatorClassName
								)}
								style={{
									...hoverStyle,
									opacity: hoveredIndex !== null ? 1 : 0,
									transition: "all 300ms ease-out",
								}}
								aria-hidden="true"
							/>
						)}

						<div
							ref={ref}
							className={cn(
								"relative flex items-center",
								stretch ? "w-full" : "",
								variant === "default" ? "space-x-[6px]" : "space-x-[2px]"
							)}
						>
							{React.Children.map(children, (child, index) => {
								if (!React.isValidElement(child)) return child;

								const childProps = (
									child as React.ReactElement<{
										value: string;
										disabled?: boolean;
										label?: string;
										className?: string;
										activeClassName?: string;
										inactiveClassName?: string;
										disabledClassName?: string;
									}>
								).props;

								const { value, disabled } = childProps;
								const isActive = value === activeValue;

								return (
									<div
										key={value}
										ref={(el) => setTabRef(el, index)}
										className={cn(
											"px-3 py-2 sm:mb-1.5 mb-2 cursor-pointer transition-colors duration-300",
											SIZE_CLASSES[size],
											variant === "pills" && isActive
												? "bg-[#0e0f1114] dark:bg-[#ffffff1a] rounded-full"
												: "",
											disabled ? "opacity-50 cursor-not-allowed" : "",
											stretch ? "flex-1 text-center" : "",
											isActive
												? childProps.activeClassName || "text-foreground dark:text-foreground"
												: childProps.inactiveClassName ||
														"text-muted-foreground dark:text-muted-foreground",
											disabled && childProps.disabledClassName,
											VARIANT_CLASSES[variant],
											childProps.className
										)}
										onMouseEnter={() => !disabled && setHoveredIndex(index)}
										onMouseLeave={() => setHoveredIndex(null)}
										onClick={() => {
											if (!disabled) {
												onValueChange(value);
												scrollTabToCenter(index);
											}
										}}
										onKeyDown={(e) => {
											if (e.key === "Enter" || e.key === " ") {
												e.preventDefault();
												if (!disabled) {
													onValueChange(value);
													scrollTabToCenter(index);
												}
											}
										}}
										role="tab"
										aria-selected={isActive}
										aria-disabled={disabled}
										aria-controls={`tabpanel-${value}`}
										id={`tab-${value}`}
										tabIndex={isActive ? 0 : -1}
									>
										<div className="whitespace-nowrap flex items-center justify-center h-full">
											{child}
										</div>
									</div>
								);
							})}
						</div>

						{showActiveIndicator && variant !== "pills" && activeIndex >= 0 && (
							<div
								className={cn(
									"absolute transition-[left,width,bottom,top] duration-300 ease-out z-10",
									ACTIVE_INDICATOR_CLASSES[variant],
									activeIndicatorPosition === "top" ? "top-[-1px]" : "bottom-[-1px]",
									activeIndicatorClassName
								)}
								style={{
									...activeStyle,
									transition: "all 300ms ease-out",
									[activeIndicatorPosition]: `${activeIndicatorOffset}px`,
								}}
								aria-hidden="true"
							/>
						)}
					</div>
				</XScrollable>
			</div>
		);
	}
);
TabsList.displayName = "TabsList";

/* ───────────────────────────
   TabsTrigger
   ─────────────────────────── */

const TabsTrigger = forwardRef<
	HTMLDivElement,
	{
		value: string;
		disabled?: boolean;
		label?: string;
		className?: string;
		activeClassName?: string;
		inactiveClassName?: string;
		disabledClassName?: string;
		children?: ReactNode;
	}
>(
	(
		{
			value,
			disabled = false,
			label,
			className,
			activeClassName,
			inactiveClassName,
			disabledClassName,
			children,
			...props
		},
		ref
	) => {
		return (
			<div ref={ref} className={cn("flex items-center", className)} {...props}>
				{label || children}
			</div>
		);
	}
);
TabsTrigger.displayName = "TabsTrigger";

/* ───────────────────────────
   TabsContent
   ─────────────────────────── */

const TabsContent = forwardRef<
	HTMLDivElement,
	{
		value: string;
		className?: string;
		children: ReactNode;
	}
>(({ value, className, children, ...props }, ref) => {
	const { activeValue } = useTabsContext();

	if (value !== activeValue) return null;
	return (
		<div
			ref={ref}
			role="tabpanel"
			id={`tabpanel-${value}`}
			aria-labelledby={`tab-${value}`}
			className={className}
			{...props}
		>
			{children}
		</div>
	);
});
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };
