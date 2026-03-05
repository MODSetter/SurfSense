/** Category dispatcher — routes a CardItem to its renderer. */
import React from "react";
import type { CardItem } from "../../types";
import type { BaseCardProps } from "./types";
import { StatContent } from "./StatContent";
import { InfoContent } from "./InfoContent";
import { QuoteContent } from "./QuoteContent";
import { ProfileContent } from "./ProfileContent";
import { ProgressContent } from "./ProgressContent";
import { FactContent } from "./FactContent";
import { DefinitionContent } from "./DefinitionContent";

export function renderCardContent(item: CardItem, props: BaseCardProps): React.ReactNode {
  switch (item.category) {
    case "stat":       return <StatContent item={item} {...props} />;
    case "info":       return <InfoContent item={item} {...props} />;
    case "quote":      return <QuoteContent item={item} {...props} />;
    case "profile":    return <ProfileContent item={item} {...props} />;
    case "progress":   return <ProgressContent item={item} {...props} />;
    case "fact":       return <FactContent item={item} {...props} />;
    case "definition": return <DefinitionContent item={item} {...props} />;
  }
}
