import { FC } from "react";
import { usePathname } from "next/navigation";
import LinkComponent from "./NavLink";
import { navConfig } from "@/lib/config/";

type NavLinksProps = {
  collapsed: boolean;
  animationDuration: number;
};

const NavLinks: FC<NavLinksProps> = ({ collapsed, animationDuration }) => {
  const pathName = usePathname();

  return (
    <div className="flex h-full flex-col justify-between">
      <div id="topNavLinks">
        {navConfig.navLinks.map((link, index) => {
          if (link.navLocation === "top") {
            const activeLink = pathName === link.href;

            return (
              <div
                key={index}
                className="px-5 text-muted-foreground transition-all duration-300 hover:text-foreground"
              >
                <LinkComponent
                  activeLink={activeLink}
                  href={link.href}
                  label={link.label}
                  icon={link.icon}
                  animationDuration={animationDuration}
                  collapsed={collapsed}
                />
              </div>
            );
          }
        })}
      </div>

      <div id="btmNavLinks">
        {navConfig.navLinks.map((link, index) => {
          if (link.navLocation === "bottom") {
            const activeLink = pathName === link.href;

            return (
              <div
                key={index}
                className="px-5 text-muted-foreground transition-all duration-300 hover:text-foreground"
              >
                <LinkComponent
                  activeLink={activeLink}
                  href={link.href}
                  label={link.label}
                  icon={link.icon}
                  animationDuration={animationDuration}
                  collapsed={collapsed}
                />
              </div>
            );
          }
        })}
      </div>
    </div>
  );
};

export default NavLinks;
