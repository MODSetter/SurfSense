"use client";

import { usePathname } from "next/navigation";
import { navConfig } from "@/lib/config";
import { ModeToggle } from "@/components/theme/mode-toggle";
import { SidebarMobile } from "../../layout-components";

const Header = () => {
  const pathName = usePathname();
  const pageTitle = navConfig.navLinks.find((elem) => {
    if (elem.href === pathName) {
      return elem.pageTitle;
    }
  });

  return (
    <div className="flex h-full w-full flex-row items-center justify-between text-foreground">
      <div className="block w-full font-medium sm:block">
        {pageTitle?.pageTitle}
      </div>
      <div className="flex h-full w-full items-center justify-end gap-4">
        <div className="block sm:hidden">
          <SidebarMobile />
        </div>
        <div className="hidden sm:block">
          <ModeToggle />
        </div>
      </div>
    </div>
  );
};

export default Header;
