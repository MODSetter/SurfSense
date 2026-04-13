import { Camera } from "lucide-react";
import { Button } from "@/routes/ui/button";
import { useToast } from "@/routes/ui/use-toast";

/**
 * Quick capture button (sticky at bottom)
 * Reuses existing capture functionality
 */
export function QuickCapture() {
    const { toast } = useToast();

    const handleCapture = async () => {
        try {
            // Get active tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            if (!tab.id) {
                throw new Error("No active tab");
            }

            // Send message to background to capture page
            chrome.runtime.sendMessage({
                type: "CAPTURE_PAGE",
                tabId: tab.id,
            });

            toast({
                title: "Page captured!",
                description: "Saved to your search space",
            });
        } catch (error) {
            console.error("Failed to capture page:", error);
            toast({
                title: "Capture failed",
                description: "Please try again",
                variant: "destructive",
            });
        }
    };

    return (
        <div className="border-t p-3 bg-background">
            <Button className="w-full" variant="outline" onClick={handleCapture}>
                <Camera className="mr-2 h-4 w-4" />
                Save Current Page
            </Button>
        </div>
    );
}
