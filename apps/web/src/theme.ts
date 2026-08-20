export type Theme = "light" | "dark";

const themeStorageKey = "gamr-theme";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark";
}

export function getPreferredTheme(): Theme {
  const stored = window.localStorage.getItem(themeStorageKey);
  if (isTheme(stored)) return stored;
  const prefersDark =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  window.localStorage.setItem(themeStorageKey, theme);
}

export function initializeTheme() {
  const stored = window.localStorage.getItem(themeStorageKey);
  if (isTheme(stored)) {
    document.documentElement.setAttribute("data-theme", stored);
  }
}
