import React, { memo } from "react";
import type { ThemeColors } from "../../../theme";
import type { GridVariant } from "../variant";
import type { CardItem } from "../types";

interface ContentItemProps {
  item: CardItem;
  vmin: number;
  variant: GridVariant;
  theme: ThemeColors;
}

const ContentItem: React.FC<ContentItemProps> = ({
  item,
  vmin,
  variant,
  theme,
}) => {
  if (!item) return null;
  const color = item.color;
  const isCenter = variant.align === "center";
  const isHoriz = variant.layout === "horizontal";
  const w = isHoriz ? vmin * 72 : vmin * 52;
  const h = isHoriz ? vmin * 32 : vmin * 38;
  const accentThick = vmin * 0.4;
  const pad = vmin * 4;

  const glowX = 50 + 40 * Math.cos((variant.glowAngle * Math.PI) / 180);
  const glowY = 50 + 40 * Math.sin((variant.glowAngle * Math.PI) / 180);

  type AccentSide = "left" | "top" | "bottom" | "right";
  const isVBar = variant.accent === "left" || variant.accent === "right";
  const accentPos: Record<AccentSide, React.CSSProperties> = {
    left: { left: 0, top: pad, bottom: pad, width: accentThick },
    right: { right: 0, top: pad, bottom: pad, width: accentThick },
    top: { top: 0, left: pad, right: pad, height: accentThick },
    bottom: { bottom: 0, left: pad, right: pad, height: accentThick },
  };

  const display = (() => {
    switch (item.category) {
      case "stat":
        return { title: item.title, value: item.value, desc: item.desc };
      case "info":
        return { title: item.title, subtitle: item.subtitle, desc: item.desc, tag: item.tag };
      case "list":
        return { title: item.title, subtitle: item.subtitle, bullets: item.bullets };
      case "quote":
        return { title: `\u201C${item.quote}\u201D`, subtitle: `\u2014 ${item.author}${item.role ? `, ${item.role}` : ""}` };
      case "comparison":
        return { title: item.title, desc: `${item.labelA}: ${item.valueA}  vs  ${item.labelB}: ${item.valueB}` };
      case "profile":
        return { title: item.name, subtitle: item.role, desc: item.desc, tag: item.tag };
      case "ranking":
        return { title: item.title, value: item.value, desc: item.desc, badge: `#${item.rank}` };
      case "keyvalue":
        return { title: item.title, bullets: item.pairs.map((p) => `${p.label}: ${p.value}`) };
      case "progress":
        return { title: item.title, value: `${item.value}${item.max ? `/${item.max}` : "%"}`, desc: item.desc };
      case "fact":
        return { title: item.statement, subtitle: item.source };
      case "step":
        return { title: item.title, desc: item.desc, badge: `${item.step}` };
      case "definition":
        return { title: item.term, desc: item.definition, subtitle: item.example ? `e.g. ${item.example}` : undefined };
    }
  })();

  const title = display.title;
  const value = "value" in display ? display.value : undefined;
  const desc = "desc" in display ? display.desc : undefined;
  const subtitle = "subtitle" in display ? display.subtitle : undefined;
  const badge = "badge" in display ? display.badge : undefined;
  const tag = "tag" in display ? display.tag : undefined;
  const bullets = "bullets" in display ? display.bullets : undefined;

  const hasValue = !!value;
  const hasDesc = !!desc;
  const hasBullets = !!bullets && bullets.length > 0;
  const isSmallLabel =
    hasValue && (variant.valueStyle === "hero" || variant.valueStyle === "colored");

  const titleEl = (
    <div
      style={{
        fontSize: isSmallLabel ? vmin * 2.1 : vmin * 3.2,
        fontWeight: isSmallLabel ? 600 : 700,
        color: isSmallLabel ? theme.textSecondary : theme.textPrimary,
        letterSpacing: isSmallLabel ? vmin * 0.06 : 0,
        textTransform: isSmallLabel ? ("uppercase" as const) : ("none" as const),
        lineHeight: 1.25,
        textAlign: isCenter ? ("center" as const) : ("left" as const),
        overflow: "hidden",
        textOverflow: "ellipsis",
        display: "-webkit-box",
        WebkitLineClamp: isSmallLabel ? 1 : 2,
        WebkitBoxOrient: "vertical" as const,
      }}
    >
      {title}
    </div>
  );

  const valueEl = hasValue ? (
    variant.valueStyle === "hero" ? (
      <div
        style={{
          fontSize: vmin * 8,
          fontWeight: 800,
          color: theme.textPrimary,
          lineHeight: 1,
          letterSpacing: `-${vmin * 0.12}px`,
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
    ) : variant.valueStyle === "colored" ? (
      <div
        style={{
          fontSize: vmin * 6,
          fontWeight: 800,
          color,
          lineHeight: 1,
          textShadow: `0 0 ${vmin * 3}px ${color}35`,
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
    ) : variant.valueStyle === "badge" ? (
      <div
        style={{
          display: "inline-flex",
          padding: `${vmin * 0.5}px ${vmin * 1.6}px`,
          borderRadius: vmin * 0.7,
          background: `${color}${theme.badgeBg}`,
          border: `1px solid ${color}${theme.badgeBorder}`,
          fontSize: vmin * 2.2,
          fontWeight: 700,
          color,
          alignSelf: isCenter ? "center" : "flex-start",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
    ) : (
      <span
        style={{
          fontSize: vmin * 3.5,
          fontWeight: 800,
          color,
          textShadow: `0 0 ${vmin * 2}px ${color}30`,
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </span>
    )
  ) : null;

  const sepEl =
    variant.separator === "line" ? (
      <div
        style={{
          width: isCenter ? vmin * 5 : vmin * 7,
          height: 2,
          background: `linear-gradient(90deg, ${isCenter ? "transparent" : color}, ${color}, transparent)`,
          borderRadius: 1,
          alignSelf: isCenter ? "center" : "flex-start",
          flexShrink: 0,
        }}
      />
    ) : variant.separator === "dots" ? (
      <div
        style={{
          display: "flex",
          gap: vmin * 0.6,
          justifyContent: isCenter ? "center" : "flex-start",
          flexShrink: 0,
        }}
      >
        {[1, 0.6, 0.3].map((op, idx) => (
          <div
            key={idx}
            style={{
              width: vmin * 0.5,
              height: vmin * 0.5,
              borderRadius: "50%",
              background: color,
              opacity: op,
            }}
          />
        ))}
      </div>
    ) : null;

  const subtitleEl = subtitle ? (
    <div
      style={{
        fontSize: vmin * 1.8,
        fontWeight: 500,
        color: theme.textSecondary,
        lineHeight: 1.3,
        textAlign: isCenter ? ("center" as const) : ("left" as const),
      }}
    >
      {subtitle}
    </div>
  ) : null;

  const badgeEl = badge ? (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: vmin * 4.5,
        height: vmin * 4.5,
        borderRadius: vmin * 1.2,
        background: `${color}${theme.badgeBg}`,
        border: `1px solid ${color}${theme.badgeBorder}`,
        fontSize: vmin * 2.2,
        fontWeight: 800,
        color,
        flexShrink: 0,
      }}
    >
      {badge}
    </div>
  ) : null;

  const tagEl = tag ? (
    <div
      style={{
        display: "inline-flex",
        padding: `${vmin * 0.3}px ${vmin * 1}px`,
        borderRadius: vmin * 0.5,
        background: `${color}${theme.badgeBg}`,
        border: `1px solid ${color}${theme.badgeBorder}`,
        fontSize: vmin * 1.4,
        fontWeight: 600,
        color,
        textTransform: "uppercase" as const,
        letterSpacing: vmin * 0.05,
        alignSelf: isCenter ? "center" : "flex-start",
      }}
    >
      {tag}
    </div>
  ) : null;

  const descEl = hasDesc ? (
    <div
      style={{
        fontSize: vmin * 1.8,
        fontWeight: 400,
        color: theme.textMuted,
        lineHeight: 1.55,
        textAlign: isCenter ? ("center" as const) : ("left" as const),
        overflow: "hidden",
        display: "-webkit-box",
        WebkitLineClamp: 3,
        WebkitBoxOrient: "vertical" as const,
      }}
    >
      {desc}
    </div>
  ) : null;

  const bulletsEl = hasBullets ? (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: vmin * 0.8,
        overflow: "hidden",
      }}
    >
      {bullets!.slice(0, 5).map((b, idx) => (
        <div
          key={idx}
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: vmin * 0.8,
            fontSize: vmin * 1.7,
            color: theme.textMuted,
            lineHeight: 1.4,
          }}
        >
          <div
            style={{
              width: vmin * 0.5,
              height: vmin * 0.5,
              borderRadius: "50%",
              background: color,
              flexShrink: 0,
              marginTop: vmin * 0.5,
            }}
          />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {b}
          </span>
        </div>
      ))}
    </div>
  ) : null;

  const primaryCol = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: vmin * 1.2,
        alignItems: isCenter ? "center" : "flex-start",
        flex: isHoriz ? "1 1 0" : undefined,
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      {badgeEl}
      {tagEl}
      {variant.valueStyle === "inline" && valueEl}
      {titleEl}
      {subtitleEl}
      {variant.valueStyle !== "inline" && valueEl}
    </div>
  );

  const secondaryCol =
    hasDesc || hasBullets || variant.separator !== "none" ? (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: vmin * 1,
          alignItems: isCenter ? "center" : "flex-start",
          flex: isHoriz ? "1 1 0" : undefined,
          minWidth: 0,
          overflow: "hidden",
        }}
      >
        {sepEl}
        {descEl}
        {bulletsEl}
      </div>
    ) : null;

  return (
    <div
      style={{
        width: w,
        height: h,
        position: "relative",
        display: "flex",
        flexDirection: isHoriz ? "row" : "column",
        alignItems: isHoriz ? "center" : isCenter ? "center" : "flex-start",
        justifyContent: isHoriz ? "flex-start" : "center",
        gap: isHoriz ? vmin * 4 : vmin * 1.5,
        padding: pad,
        fontFamily: "Inter, system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: vmin * 1.5,
          background: `radial-gradient(ellipse at ${glowX}% ${glowY}%, ${color}${theme.glowOpacity} 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: vmin * 1.5,
          border: `1px solid ${theme.border}`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          ...accentPos[variant.accent],
          borderRadius: accentThick,
          background: `linear-gradient(${isVBar ? "180deg" : "90deg"}, ${color}, ${color}30)`,
          boxShadow: `0 0 ${vmin * 1.2}px ${color}${theme.accentGlowSuffix}`,
        }}
      />
      {primaryCol}
      {secondaryCol}
    </div>
  );
};

export const MemoContentItem = memo(ContentItem);
