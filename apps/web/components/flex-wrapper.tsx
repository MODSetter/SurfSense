import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import { ReactNode, Children } from "react";

const flexVariants = cva("", {
  variants: {
    columns: {
      default: "",
      "1": "flex-1 basis-full",
      "2": "flex-1 basis-full sm:basis-[48%]",
      "3": "flex-1 basis-full sm:basis-[48%] md:basis-[32%]",
      "4": "flex-1 basis-full sm:basis-[48%] md:basis-[32%] lg:basis-[24%]",
      "5": "flex-1 basis-full sm:basis-[48%] md:basis-[32%] lg:basis-[19%]",
      "6": "flex-1 basis-full sm:basis-[48%] md:basis-[32%] lg:basis-[19%] xl:basis-[12%]",
    },
    horizontal_position: {
      start: "justify-start",
      center: "justify-center text-center",
      end: "justify-end",
      none: null,
    },
    vertical_position: {
      start: "items-start",
      center: "items-center text-center",
      end: "items-end",
      none: null,
    },
    borders: {
      default: "border rounded-md p-5",
      none: null,
    },
  },
  defaultVariants: {
    columns: "default",
    horizontal_position: "none",
    vertical_position: "none",
    borders: "none",
  },
});

export type FlexWrapperProps = VariantProps<typeof flexVariants> & {
  children: ReactNode;
  className?: string;
};

export function FlexWrapper({
  children,
  className,
  columns,
  horizontal_position,
  vertical_position,
}: FlexWrapperProps) {
  return (
    <div
      id="flex-wrapper"
      className={cn(
        // isCentered && "place-items-stretch",
        flexVariants({ horizontal_position, vertical_position }),
        "w-full flex flex-wrap gap-4",
        className,
      )}
    >
      {Children.map(children, (child, index) => (
        <div
          key={index}
          className={cn(flexVariants({ columns }), "flex min-h-full")}
        >
          {/* <div key={index} className={cn("flex min-h-full")}> */}
          {child}
        </div>
      ))}
    </div>
  );
}
