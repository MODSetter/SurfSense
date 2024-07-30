import { Icons } from "@/components/icons";

export type NavConfig = typeof navConfig;

export const navConfig = {
  navLinks: [
    {
      icon: <Icons.home className="h-5 w-5" />,
      iconMobile: <Icons.home className="h-5 w-5" />,
      label: "Overview",
      href: "/",
      pageTitle: "Overview",
      navLocation: "top",
    },
    {
      icon: <Icons.settings className="h-5 w-5" />,
      iconMobile: <Icons.settings className="h-5 w-5" />,
      label: "Settings",
      href: "/settings/",
      pageTitle: "Account settings",
      navLocation: "bottom",
    },
    {
      icon: <Icons.file className="h-5 w-5" />,
      iconMobile: <Icons.file className="h-5 w-5" />,
      label: "Help",
      href: "https://next-fast-turbo.mintlify.app/",
      pageTitle: "Documentation",
      navLocation: "bottom",
    },
  ],
};
