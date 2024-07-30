"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function LinkComponent(...props: any) {
  const activeLink = props[0].activeLink;
  const collapsed = props[0].collapsed;
  const animationDuration = props[0].animationDuration;

  return (
    <Link href={props[0].href}>
      {collapsed ? (
        <TooltipProvider delayDuration={150}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className={`flex flex-row gap-6 rounded-md py-3 font-normal ${
                  collapsed ? "justify-center" : "items-center"
                } ${activeLink ? "bg-border text-foreground" : ""}`}
              >
                <div className={collapsed ? "p-0" : "pl-4"}>
                  {props[0].icon}
                </div>
                <AnimatePresence>
                  <motion.div
                    layout
                    animate={{
                      x: collapsed ? -20 : 0,
                      y: collapsed ? 0 : 0,
                      opacity: collapsed ? 0 : 1,
                      width: collapsed ? 0 : "auto",
                      display: collapsed ? "none" : "block",
                    }}
                    transition={{ duration: animationDuration }}
                    className="text-sm"
                  >
                    {props[0].label}
                  </motion.div>
                </AnimatePresence>
              </div>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>{props[0].label}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        <div
          className={`flex flex-row gap-6 rounded-md py-3 font-normal ${
            collapsed ? "justify-center" : "items-center"
          } ${activeLink ? "bg-border text-foreground" : ""}`}
        >
          <div className={collapsed ? "p-0" : "pl-4"}>{props[0].icon}</div>
          <AnimatePresence>
            <motion.div
              layout
              animate={{
                x: collapsed ? -20 : 0,
                y: collapsed ? 0 : 0,
                opacity: collapsed ? 0 : 1,
                width: collapsed ? 0 : "auto",
                display: collapsed ? "none" : "block",
              }}
              transition={{ duration: animationDuration }}
              className="text-sm"
            >
              {props[0].label}
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </Link>
  );
}
