import { MemoryRouter } from "react-router-dom";
import { Toaster } from "@/routes/ui/toaster";
import { ChatInterface } from "./chat/ChatInterface";
import { PageContextProvider } from "./context/PageContextProvider";

/**
 * Main Side Panel Application
 * Provides AI chat interface with page context awareness
 */
export function SidePanelApp() {
    return (
        <PageContextProvider>
            <MemoryRouter>
                <div className="flex flex-col h-full">
                    {/* Main chat interface */}
                    <ChatInterface />

                    {/* Toast notifications */}
                    <Toaster />
                </div>
            </MemoryRouter>
        </PageContextProvider>
    );
}
