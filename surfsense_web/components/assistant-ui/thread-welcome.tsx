import { useAtomValue } from "jotai";
import type { FC } from "react";
import { useMemo } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Composer } from "@/components/assistant-ui/composer";

const getTimeBasedGreeting = (userEmail?: string): string => {
	const hour = new Date().getHours();

	// Extract first name from email if available
	const firstName = userEmail
		? userEmail.split("@")[0].split(".")[0].charAt(0).toUpperCase() +
			userEmail.split("@")[0].split(".")[0].slice(1)
		: null;

	// Array of greeting variations for each time period
	const morningGreetings = ["Good morning", "Fresh start today", "Morning", "Hey there"];

	const afternoonGreetings = ["Good afternoon", "Afternoon", "Hey there", "Hi there"];

	const eveningGreetings = ["Good evening", "Evening", "Hey there", "Hi there"];

	const nightGreetings = ["Good night", "Evening", "Hey there", "Winding down"];

	const lateNightGreetings = ["Still up", "Night owl mode", "Up past bedtime", "Hi there"];

	// Select a random greeting based on time
	let greeting: string;
	if (hour < 5) {
		// Late night: midnight to 5 AM
		greeting = lateNightGreetings[Math.floor(Math.random() * lateNightGreetings.length)];
	} else if (hour < 12) {
		greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
	} else if (hour < 18) {
		greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
	} else if (hour < 22) {
		greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
	} else {
		// Night: 10 PM to midnight
		greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
	}

	// Add personalization with first name if available
	if (firstName) {
		return `${greeting}, ${firstName}!`;
	}

	return `${greeting}!`;
};

export const ThreadWelcome: FC = () => {
	const { data: user } = useAtomValue(currentUserAtom);

	// Memoize greeting so it doesn't change on re-renders (only on user change)
	const greeting = useMemo(() => getTimeBasedGreeting(user?.email), [user?.email]);

	return (
		<div className="aui-thread-welcome-root mx-auto flex w-full max-w-(--thread-max-width) grow flex-col items-center px-4 relative">
			{/* Greeting positioned above the composer - fixed position */}
			<div className="aui-thread-welcome-message absolute bottom-[calc(50%+5rem)] left-0 right-0 flex flex-col items-center text-center">
				<h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-2 animate-in text-3xl md:text-5xl delay-100 duration-500 ease-out fill-mode-both">
					{greeting}
				</h1>
			</div>
			{/* Composer - top edge fixed, expands downward only */}
			<div className="fade-in slide-in-from-bottom-3 animate-in delay-200 duration-500 ease-out fill-mode-both w-full flex items-start justify-center absolute top-[calc(50%-3.5rem)] left-0 right-0">
				<Composer />
			</div>
		</div>
	);
};
