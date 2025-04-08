"use client";
import { cn } from "@/lib/utils";
import { IconMenu2, IconX, IconBrandGoogleFilled } from "@tabler/icons-react";
import {
  motion,
  AnimatePresence,
  useScroll,
  useMotionValueEvent,
} from "framer-motion";
import Link from "next/link";
import React, { useRef, useState } from "react";
import { Button } from "./ui/button";
import { Logo } from "./Logo";
import { ThemeTogglerComponent } from "./theme/theme-toggle";

interface NavbarProps {
  navItems: {
    name: string;
    link: string;
  }[];
  visible: boolean;
}

export const Navbar = () => {
  const navItems = [
    {
      name: "",
      link: "/",
    },
    // {
    //   name: "Product",
    //   link: "/#product",
    // },
    // {
    //   name: "Pricing",
    //   link: "/#pricing",
    // },
  ];

  const ref = useRef<HTMLDivElement>(null);
  const { scrollY } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const [visible, setVisible] = useState<boolean>(false);

  useMotionValueEvent(scrollY, "change", (latest) => {
    if (latest > 100) {
      setVisible(true);
    } else {
      setVisible(false);
    }
  });

  return (
    <motion.div ref={ref} className="w-full fixed top-2 inset-x-0 z-50">
      <DesktopNav visible={visible} navItems={navItems} />
      <MobileNav visible={visible} navItems={navItems} />
    </motion.div>
  );
};

const DesktopNav = ({ navItems, visible }: NavbarProps) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  
  const handleGoogleLogin = () => {
    // Redirect to Google OAuth authorization URL
    fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/google/authorize`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to get authorization URL');
        }
        return response.json();
      })
      .then((data) => {
        if (data.authorization_url) {
          window.location.href = data.authorization_url;
        } else {
          console.error('No authorization URL received');
        }
      })
      .catch((error) => {
        console.error('Error during Google login:', error);
      });
  };

  return (
    <motion.div
      onMouseLeave={() => setHoveredIndex(null)}
      animate={{
        backdropFilter: "blur(16px)",
        background: visible 
          ? "rgba(var(--background-rgb), 0.8)" 
          : "rgba(var(--background-rgb), 0.6)",
        width: visible ? "38%" : "80%",
        height: visible ? "48px" : "64px",
        y: visible ? 8 : 0,
      }}
      initial={{
        width: "80%",
        height: "64px",
        background: "rgba(var(--background-rgb), 0.6)",
      }}
      transition={{
        type: "spring",
        stiffness: 400,
        damping: 30,
      }}
      className={cn(
        "hidden lg:flex flex-row self-center items-center justify-between py-2 mx-auto px-6 rounded-full relative z-[60] backdrop-saturate-[1.8]",
        visible ? "border dark:border-white/10 border-gray-300/30" : "border-0"
      )}
      style={{
        "--background-rgb": "var(--tw-dark) ? '0, 0, 0' : '255, 255, 255'",
      } as React.CSSProperties}
    >
      <div className="flex flex-row items-center gap-2">
        <Logo className="h-8 w-8 rounded-md" /> 
        <span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
      </div>
      <motion.div
        className="lg:flex flex-row flex-1 items-center justify-center space-x-1 text-sm"
        animate={{
          scale: visible ? 0.9 : 1,
          justifyContent: visible ? "flex-end" : "center",
        }}
      >
        {navItems.map((navItem, idx) => (
          <motion.div
            key={`nav-item-${idx}`}
            onHoverStart={() => setHoveredIndex(idx)}
            className="relative"
          >
            <Link
              className="dark:text-white/90 text-gray-800 relative px-3 py-1.5 transition-colors"
              href={navItem.link}
            >
              <span className="relative z-10">{navItem.name}</span>
              {hoveredIndex === idx && (
                <motion.div
                  layoutId="menu-hover"
                  className="absolute inset-0 rounded-full dark:bg-gradient-to-r dark:from-white/10 dark:to-white/20 bg-gradient-to-r from-gray-200 to-gray-300"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{
                    opacity: 1,
                    scale: 1.1,
                    background: "var(--tw-dark) ? radial-gradient(circle at center, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.1) 50%, transparent 100%) : radial-gradient(circle at center, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.03) 50%, transparent 100%)",
                  }}
                  exit={{
                    opacity: 0,
                    scale: 0.8,
                    transition: {
                      duration: 0.2,
                    },
                  }}
                  transition={{
                    type: "spring",
                    bounce: 0.4,
                    duration: 0.4,
                  }}
                />
              )}
            </Link>
          </motion.div>
        ))}
      </motion.div>
      <div className="flex items-center gap-2">
        <ThemeTogglerComponent />
        <AnimatePresence mode="popLayout" initial={false}>
          {!visible && (
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{
                scale: 1,
                opacity: 1,
                transition: {
                  type: "spring",
                  stiffness: 400,
                  damping: 25,
                },
              }}
              exit={{
                scale: 0.8,
                opacity: 0,
                transition: {
                  duration: 0.2,
                },
              }}
            >
              <Button
                onClick={handleGoogleLogin}
                variant="outline"
                className="hidden md:flex items-center gap-2 rounded-full dark:bg-white/20 dark:hover:bg-white/30 dark:text-white bg-gray-100 hover:bg-gray-200 text-gray-800 border-0"
              >
                <IconBrandGoogleFilled className="h-4 w-4" />
                <span>Sign in with Google</span>
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

const MobileNav = ({ navItems, visible }: NavbarProps) => {
  const [open, setOpen] = useState(false);
  
  const handleGoogleLogin = () => {
    // Redirect to the login page
    window.location.href = "./login";
  };
  
  return (
    <>
      <motion.div
        animate={{
          backdropFilter: "blur(16px)",
          background: visible 
            ? "rgba(var(--background-rgb), 0.8)" 
            : "rgba(var(--background-rgb), 0.6)",
          width: visible ? "80%" : "90%",
          y: visible ? 0 : 8,
          borderRadius: open ? "24px" : "full",
          padding: "8px 16px",
        }}
        initial={{
          width: "80%",
          background: "rgba(var(--background-rgb), 0.6)",
        }}
        transition={{
          type: "spring",
          stiffness: 400,
          damping: 30,
        }}
        className={cn(
          "flex relative flex-col lg:hidden w-full justify-between items-center max-w-[calc(100vw-2rem)] mx-auto z-50 backdrop-saturate-[1.8] rounded-full",
          visible ? "border border-solid dark:border-white/40 border-gray-300/30" : "border-0"
        )}
        style={{
          "--background-rgb": "var(--tw-dark) ? '0, 0, 0' : '255, 255, 255'",
        } as React.CSSProperties}
      >
        <div className="flex flex-row justify-between items-center w-full">
        <Logo className="h-8 w-8 rounded-md" /> 
          <div className="flex items-center gap-2">
            <ThemeTogglerComponent />
            {open ? (
              <IconX className="dark:text-white/90 text-gray-800" onClick={() => setOpen(!open)} />
            ) : (
              <IconMenu2
                className="dark:text-white/90 text-gray-800"
                onClick={() => setOpen(!open)}
              />
            )}
          </div>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{
                opacity: 0,
                y: -20,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              exit={{
                opacity: 0,
                y: -20,
              }}
              transition={{
                type: "spring",
                stiffness: 400,
                damping: 30,
              }}
              className="flex rounded-3xl absolute top-16 dark:bg-black/80 bg-white/90 backdrop-blur-xl backdrop-saturate-[1.8] inset-x-0 z-50 flex-col items-start justify-start gap-4 w-full px-6 py-8"
            >
              {navItems.map(
                (navItem: { link: string; name: string }, idx: number) => (
                  <Link
                    key={`link=${idx}`}
                    href={navItem.link}
                    onClick={() => setOpen(false)}
                    className="relative dark:text-white/90 text-gray-800 hover:text-gray-900 dark:hover:text-white transition-colors"
                  >
                    <motion.span className="block">{navItem.name}</motion.span>
                  </Link>
                )
              )}
              <Button
                onClick={handleGoogleLogin}
                variant="outline"
                className="flex items-center gap-2 mt-4 w-full justify-center rounded-full dark:bg-white/20 dark:hover:bg-white/30 dark:text-white bg-gray-100 hover:bg-gray-200 text-gray-800 border-0"
              >
                <IconBrandGoogleFilled className="h-4 w-4" />
                <span>Sign in with Google</span>
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </>
  );
}; 