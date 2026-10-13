import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "projecta-theme-mode";
export const DESKTOP_THEME_URL = "http://projecta-bootstrap.localhost/preferences/theme";

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === "light" || mode === "dark") {
    return mode;
  }
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch {
      return "light";
    }
  }
  return "light";
}

export function applyDocumentTheme(resolved: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.style.colorScheme = resolved;
}

export function getStoredLocalMode(): ThemeMode {
  if (typeof window === "undefined") return "system";
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") {
      return raw;
    }
  } catch {
    // Storage access restricted or unavailable
  }
  return "system";
}

export function setStoredLocalMode(mode: ThemeMode): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Storage access restricted or unavailable
  }
}

export async function fetchDesktopThemePreference(): Promise<ThemeMode | null> {
  if (typeof window === "undefined" || window.isTauri !== true) {
    return null;
  }
  try {
    const res = await fetch(DESKTOP_THEME_URL, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Projecta-Theme-Request": "1",
      },
    });
    if (!res.ok) return null;
    const data: unknown = await res.json();
    if (data && typeof data === "object" && "themeMode" in data) {
      const mode = (data as Record<string, unknown>).themeMode;
      if (mode === "light" || mode === "dark" || mode === "system") {
        return mode;
      }
    }
  } catch {
    // Desktop preference endpoint not reachable or network error
  }
  return null;
}

export async function saveDesktopThemePreference(mode: ThemeMode): Promise<boolean> {
  if (typeof window === "undefined" || window.isTauri !== true) {
    return false;
  }
  try {
    const res = await fetch(DESKTOP_THEME_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Projecta-Theme-Request": "1",
      },
      body: JSON.stringify({ themeMode: mode }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function initEarlyTheme(): void {
  const mode = getStoredLocalMode();
  const resolved = resolveTheme(mode);
  applyDocumentTheme(resolved);
}

export interface ThemeContextValue {
  mode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setMode: (nextMode: ThemeMode) => Promise<boolean> | void;
  isDesktop: boolean;
  error: string | null;
  clearError: () => void;
}

export const ThemeContext = createContext<ThemeContextValue>({
  mode: "system",
  resolvedTheme: "light",
  setMode: () => {},
  isDesktop: false,
  error: null,
  clearError: () => {},
});

export class ThemeController {
  public mode: ThemeMode;
  public resolvedTheme: ResolvedTheme;
  public error: string | null = null;
  public isDesktop: boolean;
  private listeners = new Set<() => void>();
  private mediaListener: ((e: MediaQueryListEvent) => void) | null = null;
  private mediaQueryList: MediaQueryList | null = null;

  constructor(options?: {
    initialMode?: ThemeMode;
    isDesktop?: boolean;
    skipDesktopSync?: boolean;
  }) {
    this.isDesktop =
      options?.isDesktop ?? (typeof window !== "undefined" && window.isTauri === true);
    this.mode = options?.initialMode ?? getStoredLocalMode();
    this.resolvedTheme = resolveTheme(this.mode);
    applyDocumentTheme(this.resolvedTheme);
    this.setupMediaListener();

    if (this.isDesktop && !options?.skipDesktopSync) {
      void this.syncFromDesktop();
    }
  }

  public clearError(): void {
    this.error = null;
    this.notify();
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }

  public setupMediaListener(): void {
    this.teardownMediaListener();
    if (this.mode !== "system") return;
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;

    try {
      this.mediaQueryList = window.matchMedia("(prefers-color-scheme: dark)");
      this.mediaListener = (e: MediaQueryListEvent) => {
        if (this.mode !== "system") return;
        const nextResolved: ResolvedTheme = e.matches ? "dark" : "light";
        if (this.resolvedTheme !== nextResolved) {
          this.resolvedTheme = nextResolved;
          applyDocumentTheme(nextResolved);
          this.notify();
        }
      };
      this.mediaQueryList.addEventListener("change", this.mediaListener);
    } catch {
      // matchMedia not supported
    }
  }

  public teardownMediaListener(): void {
    if (this.mediaQueryList && this.mediaListener) {
      try {
        this.mediaQueryList.removeEventListener("change", this.mediaListener);
      } catch {
        // ignore
      }
      this.mediaListener = null;
      this.mediaQueryList = null;
    }
  }

  public async syncFromDesktop(): Promise<void> {
    try {
      const desktopMode = await fetchDesktopThemePreference();
      if (desktopMode !== null) {
        this.error = null;
        if (desktopMode !== this.mode) {
          this.mode = desktopMode;
          setStoredLocalMode(desktopMode);
          this.resolvedTheme = resolveTheme(desktopMode);
          applyDocumentTheme(this.resolvedTheme);
          this.setupMediaListener();
          this.notify();
        }
      } else {
        this.error = "Failed to load desktop theme preference.";
        this.notify();
      }
    } catch {
      this.error = "Failed to load desktop theme preference.";
      this.notify();
    }
  }

  public async setMode(nextMode: ThemeMode): Promise<boolean> {
    const previousMode = this.mode;
    const previousResolved = this.resolvedTheme;

    // Tentatively apply next mode
    this.mode = nextMode;
    this.resolvedTheme = resolveTheme(nextMode);
    applyDocumentTheme(this.resolvedTheme);
    this.setupMediaListener();
    this.error = null;
    this.notify();

    if (this.isDesktop) {
      try {
        const ok = await saveDesktopThemePreference(nextMode);
        if (!ok) {
          // Revert and report honest error: do not silently claim persisted mode
          this.mode = previousMode;
          this.resolvedTheme = previousResolved;
          applyDocumentTheme(previousResolved);
          this.setupMediaListener();
          this.error = "Failed to persist desktop theme preference.";
          this.notify();
          return false;
        }
      } catch {
        this.mode = previousMode;
        this.resolvedTheme = previousResolved;
        applyDocumentTheme(previousResolved);
        this.setupMediaListener();
        this.error = "Failed to persist desktop theme preference.";
        this.notify();
        return false;
      }
    }

    setStoredLocalMode(nextMode);
    this.notify();
    return true;
  }

  public dispose(): void {
    this.teardownMediaListener();
    this.listeners.clear();
  }
}

export function ThemeProvider({
  children,
  controller,
}: {
  children: ReactNode;
  controller?: ThemeController;
}) {
  const [ctrl] = useState(() => controller ?? new ThemeController());
  const [state, setState] = useState(() => ({
    mode: ctrl.mode,
    resolvedTheme: ctrl.resolvedTheme,
    error: ctrl.error,
    isDesktop: ctrl.isDesktop,
  }));

  useEffect(() => {
    return ctrl.subscribe(() => {
      setState({
        mode: ctrl.mode,
        resolvedTheme: ctrl.resolvedTheme,
        error: ctrl.error,
        isDesktop: ctrl.isDesktop,
      });
    });
  }, [ctrl]);

  useEffect(() => {
    return () => {
      if (!controller) {
        ctrl.dispose();
      }
    };
  }, [ctrl, controller]);

  const value: ThemeContextValue = useMemo(
    () => ({
      mode: state.mode,
      resolvedTheme: state.resolvedTheme,
      isDesktop: state.isDesktop,
      error: state.error,
      setMode: (nextMode: ThemeMode) => ctrl.setMode(nextMode),
      clearError: () => ctrl.clearError(),
    }),
    [state, ctrl],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
