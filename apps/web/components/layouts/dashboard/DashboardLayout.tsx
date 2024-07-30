import styles from "./DashboardLayout.module.css";
import { Footer, Header, Sidebar } from "./layout-components";

type DashboardLayoutProps = {
  children: React.ReactNode;
};

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div
      className={`grid h-screen text-muted-foreground ${styles.dashboardWrapper}`}
    >
      <div className={`hidden h-screen sm:block ${styles.dashboardSidebar}`}>
        <Sidebar />
      </div>
      <div className={`grid overflow-auto ${styles.dashboardMain}`}>
        <div
          className={`fixed w-screen z-50 top-0 flex h-20 items-center border-b border-border bg-background/30 px-8 backdrop-blur ${styles.dashboardHeader}`}
        >
          <Header />
        </div>
        <div className={styles.dashboardContent}>
          <div
            className={`flex flex-col px-8 ${styles.dashboardContentWrapper}`}
          >
            {children}
          </div>
          <div className="px-8">
            <Footer />
          </div>
        </div>
      </div>
    </div>
  );
}
