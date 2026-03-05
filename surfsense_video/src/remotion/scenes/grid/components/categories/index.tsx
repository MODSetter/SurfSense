import React from "react";
import type { CardItem } from "../../types";
import type { BaseCardProps } from "./types";
import { StatContent } from "./StatContent";
import { InfoContent } from "./InfoContent";
import { ListContent } from "./ListContent";
import { QuoteContent } from "./QuoteContent";
import { ComparisonContent } from "./ComparisonContent";
import { ProfileContent } from "./ProfileContent";
import { RankingContent } from "./RankingContent";
import { KeyValueContent } from "./KeyValueContent";
import { ProgressContent } from "./ProgressContent";
import { FactContent } from "./FactContent";
import { StepContent } from "./StepContent";
import { DefinitionContent } from "./DefinitionContent";

export function renderCardContent(
  item: CardItem,
  props: BaseCardProps,
): React.ReactNode {
  switch (item.category) {
    case "stat":
      return <StatContent item={item} {...props} />;
    case "info":
      return <InfoContent item={item} {...props} />;
    case "list":
      return <ListContent item={item} {...props} />;
    case "quote":
      return <QuoteContent item={item} {...props} />;
    case "comparison":
      return <ComparisonContent item={item} {...props} />;
    case "profile":
      return <ProfileContent item={item} {...props} />;
    case "ranking":
      return <RankingContent item={item} {...props} />;
    case "keyvalue":
      return <KeyValueContent item={item} {...props} />;
    case "progress":
      return <ProgressContent item={item} {...props} />;
    case "fact":
      return <FactContent item={item} {...props} />;
    case "step":
      return <StepContent item={item} {...props} />;
    case "definition":
      return <DefinitionContent item={item} {...props} />;
  }
}
