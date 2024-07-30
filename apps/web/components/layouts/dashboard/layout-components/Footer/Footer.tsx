import styles from "./Footer.module.css";

const Footer = () => {
  return (
    <footer className={`w-full text-sm ${styles.dashboardFooter}`}>
      <div>
        <div className="flex flex-col gap-4 justify-end">
          <div className="text-xs text-muted-foreground">
            Copyright© Next-Fast-Turbo. All rights reserved.
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
