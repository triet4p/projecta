import type { ReactNode } from "react";

type NavItem = { id: string; label: string; icon?: ReactNode };

export function DataWorkspaceShell({
  title,
  activeId,
  items,
  onNavigate,
  children,
}: {
  title: string;
  activeId: string;
  items: NavItem[];
  onNavigate: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="dws-shell">
      <a className="skip-link" href="#dws-main">Skip to main content</a>
      <header className="dws-topbar">
        <strong>{title}</strong>
        <label style={{ marginInline: "auto", maxWidth: 360, width: "45%" }}>
          <span className="sr-only">Search workspace</span>
          <input className="dws-input" placeholder="Search workspace…" type="search" />
        </label>
        <button aria-label="Open account menu" className="dws-button" type="button">Account</button>
      </header>
      <div className="dws-workspace">
        <nav aria-label="Primary navigation" className="dws-sidebar">
          {items.map((item) => (
            <button
              aria-current={activeId === item.id ? "page" : undefined}
              className="dws-nav-item"
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              {item.icon}<span className="dws-nav-label">{item.label}</span>
            </button>
          ))}
        </nav>
        <main className="dws-main" id="dws-main" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div aria-label="Page actions" className="dws-toolbar" role="toolbar">{children}</div>;
}

export function StatusMessage({ kind, children }: { kind: "error" | "success" | "warning"; children: ReactNode }) {
  return <div aria-live={kind === "error" ? "assertive" : "polite"} className={`dws-status dws-status--${kind}`} role={kind === "error" ? "alert" : "status"}>{children}</div>;
}
