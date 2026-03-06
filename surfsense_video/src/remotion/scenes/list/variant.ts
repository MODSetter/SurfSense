/** List scene variant — seed-deterministic visual style. */
import { random } from "remotion";

export type ListLayout = "zigzag" | "column" | "row" | "pyramid";
type ItemShape = "rounded" | "pill";
type ConnectorStyle = "line" | "dashed" | "none";
export type ListCardStyle = "accent-left" | "accent-bottom" | "filled" | "minimal";

export interface ListVariant {
  layout: ListLayout;
  itemShape: ItemShape;
  connectorStyle: ConnectorStyle;
  cardStyle: ListCardStyle;
  showIndex: boolean;
}

export function deriveListVariant(seed: number): ListVariant {
  const s = (key: string) => random(`${seed}-${key}`);
  const pick = <T,>(key: string, arr: T[]) =>
    arr[Math.floor(s(key) * arr.length)];

  return {
    layout: pick("layout", ["zigzag", "column", "row", "pyramid"] as ListLayout[]),
    itemShape: pick("shape", ["rounded", "pill"] as ItemShape[]),
    connectorStyle: pick("connector", ["line", "dashed", "none"] as ConnectorStyle[]),
    cardStyle: pick("cardStyle", ["accent-left", "accent-bottom", "filled", "minimal"] as ListCardStyle[]),
    showIndex: s("index") > 0.4,
  };
}
