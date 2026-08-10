import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AppShell({
  children,
  badges,
}: {
  children: ReactNode;
  badges?: ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="brand-bar">
        <div>
          <p className="brand-name">
            <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
              RangeMatch
            </Link>
          </p>
          <p className="brand-tag">
            Agricultural land investigation Agent — evidence before conclusion
          </p>
        </div>
        <div className="status-row" aria-label="Run context badges">
          {badges}
        </div>
      </header>
      {children}
      <p className="footer-note">
        Preliminary land screening. Confirm boundaries, water, access, and operating conditions
        before purchasing or stocking the property.
      </p>
    </div>
  );
}

export function Badge({
  kind,
  children,
}: {
  kind?: "replay" | "blocked" | "point" | "parcel" | "live";
  children: ReactNode;
}) {
  return <span className={`badge ${kind ? `badge-${kind}` : ""}`}>{children}</span>;
}
