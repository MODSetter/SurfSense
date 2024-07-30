// Example cards from ShadCN: https://github.com/shadcn-ui/ui/tree/0fae3fd93ae749aca708bdfbbbeddc5d576bfb2e/apps/www/registry/default/example/cards
import { FlexWrapper } from "@/components/flex-wrapper";
import { DemoRevenue } from "@/components/demo-revenue";
import { DemoSubscriptions } from "@/components/demo-subscriptions";
import { DemoExercise } from "@/components/demo-exercise";
import { DemoGoal } from "@/components/demo-goal";

export function CardsStats() {
  return (
    <FlexWrapper columns="4">
      <DemoRevenue />
      <DemoSubscriptions />
      <DemoExercise />
      <DemoGoal />
    </FlexWrapper>
  );
}
