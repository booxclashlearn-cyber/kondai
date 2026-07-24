import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const navigation = [
  ["/", "Overview"],
  ["/data", "Business Data"],
  ["/insights", "Insights"],
  ["/campaigns", "Campaigns"],
  ["/customers", "Customer Care"],
  ["/approvals", "Approvals"],
  ["/integrations", "Integrations"],
  ["/activity", "Activity Log"],
];

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <div className="brand-row">
            <div className="brand-mark">K</div>
            <div>
              <h1>Kondai</h1>
              <span>Founder Operations</span>
            </div>
          </div>

          <nav className="primary-navigation">
            {navigation.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          <span className="live-dot" />
          Secure workspace
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}
