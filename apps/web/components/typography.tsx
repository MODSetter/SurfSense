// WIP component. Will flesh out more as we develop

import * as React from "react";
import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const typographyVariants = cva("m-0 self-center p-0", {
  variants: {
    variant: {
      h1: "scroll-m-20 text-4xl font-extrabold tracking-tight lg:text-5xl",
      h2: "scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0",
      h3: "scroll-m-20 text-2xl font-semibold tracking-tight",
      h4: "scroll-m-20 text-xl font-semibold tracking-tight",
      p: "leading-7 [&:not(:first-child)]:mt-6",
      code: "relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm font-semibold",
      lead: "text-xl text-muted-foreground",
    },
    size: {
      default: "text-lg",
      sm: "text-sm",
      lg: "text-xl",
    },
    colour: {
      default: "text-foreground",
      muted: "text-muted-foreground",
      accent: "text-accent",
      inverted: "text-background",
    },
  },
  defaultVariants: {
    variant: "p",
    size: "default",
    colour: "default",
  },
});

export interface TypographyProps
  extends React.HTMLAttributes<HTMLHeadingElement>,
    VariantProps<typeof typographyVariants> {
  children: React.ReactNode;
}

const Typography = ({
  variant,
  size,
  colour,
  className,
  children,
}: TypographyProps) => {
  let HeadingComponent: React.ElementType = "div";

  switch (variant) {
    case "h1":
      HeadingComponent = "h1";
      break;
    case "h2":
      HeadingComponent = "h2";
      break;
    case "h3":
      HeadingComponent = "h3";
      break;
    case "h4":
      HeadingComponent = "h4";
      break;
    case "p":
      HeadingComponent = "p";
      break;
    case "code":
      HeadingComponent = "code";
      break;
  }

  return (
    <HeadingComponent
      className={cn(typographyVariants({ variant, size, className, colour }))}
    >
      {children}
    </HeadingComponent>
  );
};

export { Typography, typographyVariants as buttonVariants };
