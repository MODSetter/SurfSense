"use client";
import { useEffect } from "react";
import { useState } from "react";
import Link from "next/link";
import { Icons } from "@/components/icons";
import { motion } from "framer-motion";
import NavLinks from "./NavLinks";

const Sidebar = () => {
  const [collapsed, setCollapsed] = useState(false);
  const animationDuration = 0.4;
  const sideBarWidth = "250px";

  // Load collapsed state from localStorage on component mount
  useEffect(() => {
    const collapsedState = localStorage.getItem("sidebarCollapsed");
    if (collapsedState !== null) {
      setCollapsed(collapsedState === "true" ? true : false);
    }
  }, []);

  const handleClose = () => {
    localStorage.setItem("sidebarCollapsed", (!collapsed).toString());
    setCollapsed(!collapsed);
  };

  return (
    <motion.div
      layout
      initial={{ width: collapsed ? "88px" : sideBarWidth }}
      animate={{
        minWidth: collapsed ? "88px" : sideBarWidth,
        width: collapsed ? "88px" : sideBarWidth,
      }}
      transition={{ duration: animationDuration }}
      id="sidebar"
      className={`flex h-full flex-col justify-between gap-8 border-r border-border`}
    >
      <div
        className={`flex h-20 items-center justify-between border-b border-border ${
          collapsed ? "px-8" : "px-4"
        } `}
      >
        <Link href="/">
          <motion.div
            layout
            animate={{
              x: collapsed ? -100 : 0,
              y: collapsed ? 0 : 0,
              opacity: collapsed ? 0 : 1,
              width: collapsed ? 0 : "auto",
              display: collapsed ? "none" : "block",
            }}
            transition={{ duration: animationDuration }}
          >
            <div className="flex flex-row items-center gap-1 font-semibold text-sm text-foreground">
              <span>
                <Icons.logo className="h-5" />
              </span>
              Next-Fast-Turbo
            </div>
          </motion.div>
        </Link>

        {collapsed ? (
          <Icons.panelLeftOpen
            className="h-6 w-6 cursor-pointer text-muted-foreground transition-all hover:text-foreground hover:duration-300"
            onClick={handleClose}
          />
        ) : (
          <Icons.panelLeftClose
            className="h-6 w-6 cursor-pointer text-muted-foreground transition-all hover:text-foreground hover:duration-300"
            onClick={handleClose}
          />
        )}
      </div>
      <div className="flex-1 border-border pb-8">
        <NavLinks collapsed={collapsed} animationDuration={animationDuration} />
      </div>
    </motion.div>
  );
};

export default Sidebar;
