import { SidePanelApp } from "./sidepanel/index";
import "./tailwind.css";

/**
 * Side Panel entry point for SurfSense Extension
 * Opens as a Chrome Side Panel (not popup) for better UX
 */
function IndexSidePanel() {
    return (
        <div className="h-screen w-full bg-background text-foreground">
            <SidePanelApp />
        </div>
    );
}

export default IndexSidePanel;
