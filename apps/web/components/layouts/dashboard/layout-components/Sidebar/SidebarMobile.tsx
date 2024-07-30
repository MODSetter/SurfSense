"use client";
import { useRef } from "react";
import { useState } from "react";
import { Squash as Hamburger } from "hamburger-react";
import { useClickAway } from "react-use";
import { navConfig } from "@/lib/config/";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";

const SidebarMobile = () => {
  const [isOpen, setOpen] = useState(false);
  const ref = useRef(null);

  useClickAway(ref, () => setOpen(false));

  return (
    <div ref={ref}>
      <Hamburger toggled={isOpen} size={20} toggle={setOpen} />
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed left-0 w-[85%] py-12 h-screen px-8 bg-background"
          >
            <ul className="grid min-h-72 content-evenly">
              {navConfig.navLinks.map((link, index) => {
                return (
                  <motion.li
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{
                      type: "spring",
                      stiffness: 260,
                      damping: 20,
                      delay: 0.1 + index / 10,
                    }}
                    key={link.pageTitle}
                    className="w-full"
                  >
                    <Link href={link.href}>{link.pageTitle}</Link>
                    <Separator className="my-2" />
                  </motion.li>
                );
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SidebarMobile;
