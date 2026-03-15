"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";
import {
  FileText,
  Globe,
  Code2,
  Newspaper,
  Database,
  File,
  ExternalLink,
} from "lucide-react";
import { cn, Popover, PopoverContent, PopoverTrigger } from "./_adapter";

import { openSafeNavigationHref, sanitizeHref } from "../shared/media";
import type {
  SerializableCitation,
  CitationType,
  CitationVariant,
} from "./schema";

const FALLBACK_LOCALE = "en-US";

const TYPE_ICONS: Record<CitationType, LucideIcon> = {
  webpage: Globe,
  document: FileText,
  article: Newspaper,
  api: Database,
  code: Code2,
  other: File,
};

function extractDomain(url: string): string | undefined {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace(/^www\./, "");
  } catch {
    return undefined;
  }
}

function formatDate(isoString: string, locale: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
    });
  } catch {
    return isoString;
  }
}

function useHoverPopover(delay = 100) {
  const [open, setOpen] = React.useState(false);
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = React.useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setOpen(true), delay);
  }, [delay]);

  const handleMouseLeave = React.useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setOpen(false), delay);
  }, [delay]);

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return { open, setOpen, handleMouseEnter, handleMouseLeave };
}

export interface CitationProps extends SerializableCitation {
  variant?: CitationVariant;
  className?: string;
  onNavigate?: (href: string, citation: SerializableCitation) => void;
}

export function Citation(props: CitationProps) {
  const { variant = "default", className, onNavigate, ...serializable } = props;

  const {
    id,
    href: rawHref,
    title,
    snippet,
    domain: providedDomain,
    favicon,
    author,
    publishedAt,
    type = "webpage",
    locale: providedLocale,
  } = serializable;

  const locale = providedLocale ?? FALLBACK_LOCALE;
  const sanitizedHref = sanitizeHref(rawHref);
  const domain = providedDomain ?? extractDomain(rawHref);

  const citationData: SerializableCitation = {
    ...serializable,
    href: sanitizedHref ?? rawHref,
    domain,
    locale,
  };

  const TypeIcon = TYPE_ICONS[type] ?? Globe;

  const handleClick = () => {
    if (!sanitizedHref) return;
    if (onNavigate) {
      onNavigate(sanitizedHref, citationData);
    } else {
      openSafeNavigationHref(sanitizedHref);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (sanitizedHref && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      handleClick();
    }
  };

  const iconElement = favicon ? (
    <img
      src={favicon}
      alt=""
      aria-hidden="true"
      width={14}
      height={14}
      className="bg-muted size-3.5 shrink-0 rounded object-cover"
    />
  ) : (
    <TypeIcon className="size-3.5 shrink-0 opacity-60" aria-hidden="true" />
  );

  const { open, handleMouseEnter, handleMouseLeave } = useHoverPopover();

  // Inline variant: compact chip with hover popover
  if (variant === "inline") {
    return (
      <Popover open={open}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={title}
            data-tool-ui-id={id}
            data-slot="citation"
            onClick={handleClick}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            className={cn(
              "inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1",
              "bg-muted/60 text-sm outline-none",
              "transition-colors duration-150",
              "hover:bg-muted",
              "focus-visible:ring-ring focus-visible:ring-2",
              className,
            )}
          >
            {iconElement}
            <span className="text-muted-foreground">{domain}</span>
          </button>
        </PopoverTrigger>
        <PopoverContent
          side="top"
          align="start"
          className="w-72 cursor-pointer p-0"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onOpenAutoFocus={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => e.preventDefault()}
          onClick={handleClick}
        >
          <div className="hover:bg-muted/50 flex flex-col gap-2 p-3 transition-colors">
            <div className="flex items-start gap-2">
              {iconElement}
              <span className="text-muted-foreground text-xs">{domain}</span>
            </div>
            <p className="text-sm leading-snug font-medium">{title}</p>
            {snippet && (
              <p className="text-muted-foreground line-clamp-2 text-xs leading-relaxed">
                {snippet}
              </p>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  }

  // Default variant: full card
  return (
    <article
      className={cn("relative w-full max-w-md min-w-72", className)}
      lang={locale}
      data-tool-ui-id={id}
      data-slot="citation"
    >
      <div
        className={cn(
          "group @container relative isolate flex w-full min-w-0 flex-col overflow-hidden rounded-xl",
          "border-border bg-card border text-sm shadow-xs",
          "transition-colors duration-150",
          sanitizedHref && [
            "cursor-pointer",
            "hover:border-foreground/25",
            "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
          ],
        )}
        onClick={sanitizedHref ? handleClick : undefined}
        role={sanitizedHref ? "link" : undefined}
        tabIndex={sanitizedHref ? 0 : undefined}
        onKeyDown={handleKeyDown}
      >
        <div className="flex flex-col gap-2 p-4">
          <div className="text-muted-foreground flex min-w-0 items-center justify-between gap-1.5 text-xs">
            <div className="flex min-w-0 items-center gap-1.5">
              {iconElement}
              <span className="truncate font-medium">{domain}</span>
              {(author || publishedAt) && (
                <span className="opacity-70">
                  <span className="opacity-60"> — </span>
                  {author}
                  {author && publishedAt && ", "}
                  {publishedAt && (
                    <time dateTime={publishedAt} className="tabular-nums">
                      {formatDate(publishedAt, locale)}
                    </time>
                  )}
                </span>
              )}
            </div>
            {sanitizedHref && (
              <ExternalLink className="size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
            )}
          </div>

          <h3 className="text-foreground text-[15px] leading-snug font-medium text-pretty">
            <span className="group-hover:decoration-foreground/30 line-clamp-2 group-hover:underline group-hover:underline-offset-2">
              {title}
            </span>
          </h3>

          {snippet && (
            <p className="text-muted-foreground text-[13px] leading-relaxed text-pretty">
              <span className="line-clamp-3">{snippet}</span>
            </p>
          )}
        </div>
      </div>
    </article>
  );
}
