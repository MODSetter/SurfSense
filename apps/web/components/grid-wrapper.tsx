import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import { ReactNode, Children } from "react";

const gridVariants = cva("w-full grid gap-4 justify-between", {
  variants: {
    columns: {
      default:
        "grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6",
      "1": "grid-cols-1",
      "2": "grid-cols-1 sm:grid-cols-2",
      "3": "grid-cols-1 sm:grid-cols-2 md:grid-cols-3",
      "4": "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4",
      "5": "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5",
      "6": "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6",
    },
    horizontal_position: {
      start: "justify-start",
      center: "justify-center text-center",
      end: "justify-end",
    },
    vertical_position: {
      start: "items-start",
      center: "items-center text-center",
      end: "items-end",
    },
    borders: {
      default: "border rounded-md p-5",
      none: null,
    },
  },
  defaultVariants: {
    columns: "default",
    horizontal_position: "center",
    vertical_position: "center",
    borders: "none",
  },
});

export type GridWrapperProps = VariantProps<typeof gridVariants> & {
  children: ReactNode;
  className?: string;
};

export function GridWrapper({
  children,
  className,
  columns,
  horizontal_position,
  vertical_position,
}: GridWrapperProps) {
  const isCentered =
    horizontal_position === "center" && vertical_position === "center";

  return (
    <div
      className={cn(
        isCentered && "place-items-stretch",
        gridVariants({ columns, horizontal_position, vertical_position }),
        className,
      )}
    >
      {Children.map(children, (child, index) => (
        <div key={index} className={cn("flex min-h-full")}>
          {child}
        </div>
      ))}
    </div>
  );
}
