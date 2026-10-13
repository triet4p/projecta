import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getStoredLocalMode,
  resolveTheme,
  setStoredLocalMode,
  ThemeController,
  THEME_STORAGE_KEY,
} from "./theme";
import "./desktop-shell";

describe("Theme resolution and persistence", () => {
  let store: Record<string, string> = {};
  const mockLocalStorage = {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };

  const attributes: Record<string, string> = {};
  const styleObj: Record<string, string> = {};
  const mockDoc = {
    documentElement: {
      getAttribute: vi.fn((name: string) => attributes[name] ?? null),
      setAttribute: vi.fn((name: string, value: string) => {
        attributes[name] = value;
      }),
      style: styleObj,
    },
  };

  let mediaListeners: ((e: MediaQueryListEvent) => void)[] = [];
  let prefersDark = false;

  const mockWin = {
    localStorage: mockLocalStorage,
    matchMedia: vi.fn((query: string) => ({
      get matches() {
        return prefersDark;
      },
      media: query,
      addEventListener: vi.fn((event: string, cb: (e: MediaQueryListEvent) => void) => {
        if (event === "change") {
          mediaListeners.push(cb);
        }
      }),
      removeEventListener: vi.fn((event: string, cb: (e: MediaQueryListEvent) => void) => {
        if (event === "change") {
          mediaListeners = mediaListeners.filter((l) => l !== cb);
        }
      }),
    })),
    isTauri: undefined as boolean | undefined,
  };

  const fireMediaChange = (dark: boolean) => {
    prefersDark = dark;
    for (const listener of [...mediaListeners]) {
      listener({ matches: dark, media: "(prefers-color-scheme: dark)" } as MediaQueryListEvent);
    }
  };

  beforeEach(() => {
    store = {};
    mediaListeners = [];
    prefersDark = false;
    for (const key of Object.keys(attributes)) {
      delete attributes[key];
    }
    vi.restoreAllMocks();
    mockWin.matchMedia = vi.fn((query: string) => ({
      get matches() {
        return prefersDark;
      },
      media: query,
      addEventListener: vi.fn((event: string, cb: (e: MediaQueryListEvent) => void) => {
        if (event === "change") {
          mediaListeners.push(cb);
        }
      }),
      removeEventListener: vi.fn((event: string, cb: (e: MediaQueryListEvent) => void) => {
        if (event === "change") {
          mediaListeners = mediaListeners.filter((l) => l !== cb);
        }
      }),
    }));
    vi.stubGlobal("window", mockWin);
    vi.stubGlobal("document", mockDoc);
    vi.stubGlobal("localStorage", mockLocalStorage);
    mockWin.isTauri = undefined;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves explicit light and dark modes regardless of OS preference", () => {
    mockWin.matchMedia.mockImplementation((query: string) => ({
      matches: query.includes("dark"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("resolves system mode based on matchMedia dark query", () => {
    mockWin.matchMedia.mockImplementation((query: string) => ({
      matches: query.includes("dark"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    expect(resolveTheme("system")).toBe("dark");

    mockWin.matchMedia.mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    expect(resolveTheme("system")).toBe("light");
  });

  it("defaults to system when stored preference is absent or unrecognized", () => {
    expect(getStoredLocalMode()).toBe("system");

    store[THEME_STORAGE_KEY] = "unrecognized-mode";
    expect(getStoredLocalMode()).toBe("system");
  });

  it("persists and reads valid stored mode in localStorage", () => {
    setStoredLocalMode("dark");
    expect(getStoredLocalMode()).toBe("dark");
    expect(store[THEME_STORAGE_KEY]).toBe("dark");

    setStoredLocalMode("light");
    expect(getStoredLocalMode()).toBe("light");

    setStoredLocalMode("system");
    expect(getStoredLocalMode()).toBe("system");
  });

  it("handles storage exceptions gracefully when localStorage throws", () => {
    mockLocalStorage.getItem.mockImplementationOnce(() => {
      throw new Error("SecurityError: Access is denied");
    });
    expect(getStoredLocalMode()).toBe("system");

    mockLocalStorage.setItem.mockImplementationOnce(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => setStoredLocalMode("dark")).not.toThrow();
  });

  it("applies system OS dark/light changes live when mode is system", () => {
    prefersDark = false;
    const controller = new ThemeController({ initialMode: "system", isDesktop: false });
    expect(controller.resolvedTheme).toBe("light");
    expect(attributes["data-theme"]).toBe("light");

    fireMediaChange(true);
    expect(controller.resolvedTheme).toBe("dark");
    expect(attributes["data-theme"]).toBe("dark");

    fireMediaChange(false);
    expect(controller.resolvedTheme).toBe("light");
    expect(attributes["data-theme"]).toBe("light");

    controller.dispose();
  });

  it("ignores OS color scheme changes when mode is explicit light or dark", async () => {
    prefersDark = false;
    const controller = new ThemeController({ initialMode: "light", isDesktop: false });
    expect(controller.resolvedTheme).toBe("light");

    fireMediaChange(true);
    expect(controller.resolvedTheme).toBe("light");
    expect(attributes["data-theme"]).toBe("light");

    await controller.setMode("dark");
    expect(controller.resolvedTheme).toBe("dark");
    expect(attributes["data-theme"]).toBe("dark");

    fireMediaChange(false);
    expect(controller.resolvedTheme).toBe("dark");
    expect(attributes["data-theme"]).toBe("dark");

    controller.dispose();
  });

  it("adopts current OS color scheme immediately when switching back to system", async () => {
    prefersDark = true;
    const controller = new ThemeController({ initialMode: "light", isDesktop: false });
    expect(controller.resolvedTheme).toBe("light");
    expect(attributes["data-theme"]).toBe("light");

    await controller.setMode("system");
    expect(controller.mode).toBe("system");
    expect(controller.resolvedTheme).toBe("dark");
    expect(attributes["data-theme"]).toBe("dark");

    controller.dispose();
  });

  it("removes media query listeners on mode switch and dispose", async () => {
    prefersDark = false;
    const controller = new ThemeController({ initialMode: "system", isDesktop: false });
    expect(mediaListeners.length).toBe(1);

    await controller.setMode("dark");
    expect(mediaListeners.length).toBe(0);

    await controller.setMode("system");
    expect(mediaListeners.length).toBe(1);

    controller.dispose();
    expect(mediaListeners.length).toBe(0);
  });

  it("reverts mode, leaves storage unpersisted, and presents honest error on desktop write failure", async () => {
    mockWin.isTauri = true;
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network connection refused"));

    store[THEME_STORAGE_KEY] = "light";
    const controller = new ThemeController({
      initialMode: "light",
      isDesktop: true,
      skipDesktopSync: true,
    });
    expect(controller.mode).toBe("light");
    expect(controller.error).toBeNull();

    const ok = await controller.setMode("dark");
    expect(ok).toBe(false);
    expect(controller.mode).toBe("light");
    expect(controller.resolvedTheme).toBe("light");
    expect(attributes["data-theme"]).toBe("light");
    expect(store[THEME_STORAGE_KEY]).toBe("light");
    expect(controller.error).toBe("Failed to persist desktop theme preference.");

    controller.dispose();
  });

  it("presents honest error and preserves current mode when desktop read fails", async () => {
    mockWin.isTauri = true;
    store[THEME_STORAGE_KEY] = "dark";
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: "INTERNAL" }),
    } as Response);

    const controller = new ThemeController({
      initialMode: "dark",
      isDesktop: true,
      skipDesktopSync: true,
    });
    expect(controller.mode).toBe("dark");

    await controller.syncFromDesktop();
    expect(controller.mode).toBe("dark");
    expect(controller.error).toBe("Failed to load desktop theme preference.");

    controller.dispose();
  });
});
