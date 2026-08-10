import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { getSidebarCollapsed, persistSidebarCollapsed } from "../sidebar";
import { applyTheme, getPreferredTheme, type Theme } from "../theme";

export function App() {
  const [theme, setTheme] = useState<Theme>(() => getPreferredTheme());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    getSidebarCollapsed(),
  );
  const location = useLocation();
  const context = location.pathname.startsWith("/datasets")
    ? "Dataset catalog"
    : location.pathname.startsWith("/experiments")
      ? "Experiment configuration"
      : location.pathname.startsWith("/runs")
        ? "Run review"
        : "Run operations";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    applyTheme(nextTheme);
  };

  const toggleSidebar = () => {
    const nextCollapsed = !sidebarCollapsed;
    setSidebarCollapsed(nextCollapsed);
    persistSidebarCollapsed(nextCollapsed);
  };

  return (
    <div className={`shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="GAMR application navigation">
        <div className="sidebar-inner">
          <div className="sidebar-top">
            <Link to="/" className="brand" aria-label="GAMR home">
              <img className="brand-mark" src="/favicon.svg" alt="" />
              <span>GAMR</span>
            </Link>
            <button
              className="sidebar-toggle"
              type="button"
              onClick={toggleSidebar}
              aria-label={`${sidebarCollapsed ? "Show" : "Hide"} navigation menu`}
              aria-expanded={!sidebarCollapsed}
            >
              <span aria-hidden="true">{sidebarCollapsed ? "›" : "‹"}</span>
            </button>
          </div>
          <div className="sidebar-health">
            <span
              className="status-dot status-dot-success"
              aria-hidden="true"
            />
            <span>Local API</span>
          </div>
          <p className="sidebar-label">Workspace</p>
          <nav className="primary-nav" aria-label="Primary navigation">
            <NavLink
              to="/"
              end
              aria-label="Dashboard"
              data-short="⌂"
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-label">Dashboard</span>
            </NavLink>
            <NavLink
              to="/datasets"
              aria-label="Datasets"
              data-short="▦"
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-label">Datasets</span>
            </NavLink>
            <NavLink
              to="/experiments/new"
              aria-label="Execute experiment"
              data-short="+"
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-label">Execute</span>
            </NavLink>
          </nav>
          <div className="sidebar-spacer" />
          <div className="sidebar-footer">
            <p className="sidebar-label">Current context</p>
            <p className="sidebar-context">{context}</p>
            <button
              className="button button-ghost theme-toggle"
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              <span aria-hidden="true">{theme === "dark" ? "☼" : "◐"}</span>
              <span>Use {theme === "dark" ? "light" : "dark"} theme</span>
            </button>
          </div>
        </div>
      </aside>
      <div className="app-frame">
        <header className="app-header">
          <div className="header-inner">
            <div className="header-context">
              <p className="eyebrow">GAMR control room</p>
              <span>{context}</span>
            </div>
            <span className="header-hint mono">no auto-approval</span>
          </div>
        </header>
        <main id="main-content" className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
