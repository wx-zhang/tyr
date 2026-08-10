const sidebarStorageKey = "gamr-sidebar-collapsed";

export function getSidebarCollapsed() {
  return window.localStorage.getItem(sidebarStorageKey) === "true";
}

export function persistSidebarCollapsed(collapsed: boolean) {
  window.localStorage.setItem(sidebarStorageKey, String(collapsed));
}
