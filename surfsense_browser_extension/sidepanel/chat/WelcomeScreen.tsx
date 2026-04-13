import { useMemo } from "react";
import { cn } from "~/lib/utils";
import { SuggestionCard, DEFAULT_CRYPTO_SUGGESTIONS } from "../components/shared";

export interface WelcomeScreenProps {
    /** User's display name for personalized greeting */
    userName?: string;
    /** Callback when a suggestion is clicked */
    onSuggestionClick?: (text: string) => void;
    /** Custom suggestions (overrides defaults) */
    suggestions?: Array<{ text: string; type: "general" | "safety" | "trending" | "wallet" | "custom" }>;
    /** Additional class names */
    className?: string;
}

/**
 * Get time-based greeting message
 */
function getTimeBasedGreeting(userName?: string): string {
    const hour = new Date().getHours();

    // Greeting variations for each time period
    const morningGreetings = ["Good morning", "Fresh start today", "Morning"];
    const afternoonGreetings = ["Good afternoon", "Afternoon", "Hey there"];
    const eveningGreetings = ["Good evening", "Evening", "Hey there"];
    const nightGreetings = ["Good night", "Evening", "Winding down"];
    const lateNightGreetings = ["Still up?", "Night owl mode", "Burning the midnight oil"];

    let greeting: string;
    if (hour < 5) {
        greeting = lateNightGreetings[Math.floor(Math.random() * lateNightGreetings.length)];
    } else if (hour < 12) {
        greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
    } else if (hour < 18) {
        greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
    } else if (hour < 22) {
        greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
    } else {
        greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
    }

    // Add personalization with name if available
    if (userName) {
        const firstName = userName.split(/\s+/)[0];
        return `${greeting}, ${firstName}!`;
    }

    return `${greeting}!`;
}

/**
 * WelcomeScreen - Displays greeting and suggestion cards for new conversations
 * 
 * Features:
 * - Time-based personalized greeting
 * - Crypto-specific suggestion cards
 * - Animated entrance
 * - Accessible keyboard navigation
 */
export function WelcomeScreen({
    userName,
    onSuggestionClick,
    suggestions = DEFAULT_CRYPTO_SUGGESTIONS,
    className,
}: WelcomeScreenProps) {
    // Memoize greeting so it doesn't change on re-renders
    const greeting = useMemo(() => getTimeBasedGreeting(userName), [userName]);

    return (
        <div
            className={cn(
                "flex flex-col items-center justify-center h-full p-4",
                "animate-in fade-in slide-in-from-bottom-4 duration-500",
                className
            )}
        >
            {/* Logo and Greeting */}
            <div className="text-center mb-8">
                <div className="text-5xl mb-4">🌊</div>
                <h1 className="text-2xl font-semibold mb-2 animate-in fade-in slide-in-from-bottom-2 duration-500 delay-100">
                    {greeting}
                </h1>
                <p className="text-muted-foreground text-sm animate-in fade-in slide-in-from-bottom-2 duration-500 delay-200">
                    Your AI co-pilot for crypto research and analysis
                </p>
            </div>

            {/* Suggestion Cards */}
            <div className="w-full max-w-sm space-y-2 animate-in fade-in slide-in-from-bottom-3 duration-500 delay-300">
                <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1">
                    <span>💡</span>
                    <span>Try asking:</span>
                </p>
                {suggestions.slice(0, 4).map((suggestion, index) => (
                    <SuggestionCard
                        key={index}
                        text={suggestion.text}
                        type={suggestion.type}
                        onClick={onSuggestionClick}
                        className="animate-in fade-in slide-in-from-bottom-2 duration-300"
                        style={{ animationDelay: `${400 + index * 100}ms` } as React.CSSProperties}
                    />
                ))}
            </div>

            {/* Footer hint */}
            <p className="text-xs text-muted-foreground mt-6 animate-in fade-in duration-500 delay-700">
                Press <kbd className="px-1.5 py-0.5 rounded bg-muted text-xs">⌘K</kbd> for quick actions
            </p>
        </div>
    );
}

