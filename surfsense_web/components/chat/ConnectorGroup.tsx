"use client";

import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
  DialogHeader
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

export interface ConnectorGroupItem {
  id: string | number;
  name: string;
  type: string;
}

interface ConnectorGroupProps {
  connectors: ConnectorGroupItem[];
  className?: string;
  iconSize?: string;
}

export const ConnectorGroup = ({ connectors, className, iconSize = "h-5 w-5" }: ConnectorGroupProps) => {
  const numDisplay = 3;
  const showExtra = connectors.length > numDisplay;
  const visible = connectors.slice(0, numDisplay);
  const extra = connectors.length - numDisplay;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <div
          className={cn("relative flex items-center ml-1 cursor-pointer group", className)}
          tabIndex={0}
          aria-label="Show all connected connectors"
        >
          {visible.map((c, idx) => (
            <div
              key={c.id}
              className={cn(
                "absolute border-[.5px] border-ring bg-muted size-7 flex items-center justify-center rounded-full transition-all",
                showExtra && idx === visible.length - 1 ? "" : ""
              )}
              style={{ left: `${idx * 18}px`, zIndex: idx + 1 }}
              title={c.name}
            >
              {getConnectorIcon(c.type, iconSize)}
            </div>
          ))}
          {showExtra && (
            <div
              className="absolute size-7 flex items-center justify-center rounded-full bg-muted border-[.5px] border-ring text-xs font-bold text-muted-foreground group-hover:bg-accent transition-colors"
              style={{ left: `${numDisplay * 18}px`, zIndex: visible.length + 1 }}
              aria-label={`+${extra} more`}
            >
              +{extra}
            </div>
          )}
        </div>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>All Connectors</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-2 overflow-y-auto">
          {connectors.map((c) => (
            <div
              key={c.id}
              className="group relative flex items-center gap-3 p-3 rounded-lg border transition-all bg-background shadow-sm hover:shadow-md"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted border-[.5px] border-ring">
                {getConnectorIcon(c.type, "h-5 w-5")}
              </div>
              <div className="min-w-0 flex-1 text-left">
                <div className="text-sm font-medium truncate text-foreground">{c.name}</div>
                <div className="text-xs text-muted-foreground truncate mt-0.5">{c.type}</div>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

