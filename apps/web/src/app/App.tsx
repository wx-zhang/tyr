import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { getSidebarCollapsed, persistSidebarCollapsed } from "../sidebar";
import { applyTheme, getPreferredTheme, type Theme } from "../theme";

function TyrMark() {
  return (
    <svg
      className="tyr-mark-svg"
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
    >
      <circle
        cx="16"
        cy="16"
        r="13"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.25"
      />
      <path
        fill="currentColor"
        d="M16 6.5 22.75 17h-3.4v8.5h-6.7V17h-3.4L16 6.5Z"
      />
    </svg>
  );
}

export function App() {
  const [theme, setTheme] = useState<Theme>(() => getPreferredTheme());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    getSidebarCollapsed(),
  );
  const location = useLocation();
  const context = location.pathname.startsWith("/tasks")
    ? "Task catalog"
    : location.pathname.startsWith("/experiments")
      ? "Experiment Preset"
      : location.pathname.startsWith("/runs/") && location.pathname !== "/runs/"
        ? "Experiment review"
        : "Experiment operations";

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
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
      <aside
        className="sidebar"
        aria-label="GAMR for Tyr application navigation"
      >
        <div className="sidebar-inner">
          <div className="sidebar-top">
            <Link to="/" className="brand" aria-label="GAMR home">
              <img className="brand-mark" src="/favicon.svg" alt="" />
              <span className="brand-text">
                <span className="brand-name">GAMR</span>
                <span className="brand-tagline">Tyr&apos;s final opponent</span>
              </span>
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
              to="/runs"
              end
              aria-label="Experiments"
              aria-current={location.pathname === "/" ? "page" : undefined}
              data-short="⌂"
              className={({ isActive }) =>
                isActive || location.pathname === "/"
                  ? "nav-link active"
                  : "nav-link"
              }
            >
              <span className="nav-label">Experiments</span>
            </NavLink>
            <NavLink
              to="/tasks"
              aria-label="Tasks"
              data-short="▦"
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-label">Tasks</span>
            </NavLink>
            <NavLink
              to="/experiments/new"
              aria-label="Run Experiment"
              data-short="+"
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-label">Run Experiment</span>
            </NavLink>
          </nav>
          <div className="sidebar-spacer" />
          <div className="sidebar-footer">
            <p className="sidebar-label">Current context</p>
            <p className="sidebar-context">{context}</p>
            <a
              className="tyr-link"
              href="https://tyr.ai/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Tyr website (opens in a new tab)"
            >
              <span className="tyr-mark" aria-hidden="true">
                <TyrMark />
              </span>
              <span className="tyr-link-text">
                <span className="tyr-link-label">Red team for Tyr</span>
                <span className="tyr-link-url">tyr.ai</span>
              </span>
            </a>
            <button
              className="button button-ghost theme-toggle"
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={theme === "dark" ? "Light theme" : "Dark theme"}
            >
              <span aria-hidden="true">{theme === "dark" ? "☼" : "◐"}</span>
              <span>{theme === "dark" ? "Light" : "Dark"}</span>
            </button>
          </div>
        </div>
      </aside>
      <div className="app-frame">
        <header className="app-header">
          <div className="header-inner">
            <div className="header-context">
              <p className="eyebrow">Red team for Tyr</p>
              <span>{context}</span>
            </div>
          </div>
        </header>
        <main id="main-content" className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
