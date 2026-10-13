import type { ReactElement } from "react";
import { useTheme, type ThemeMode } from "./theme";

export function ThemeSelector({ className }: { className?: string }): ReactElement {
  const { mode, setMode } = useTheme();

  const options: { mode: ThemeMode; label: string; title: string }[] = [
    { mode: "light", label: "Light", title: "Light color scheme" },
    { mode: "dark", label: "Dark", title: "Dark color scheme" },
    { mode: "system", label: "System", title: "Follow system color scheme" },
  ];

  return (
    <div
      aria-label="Color scheme preference"
      className={className ? `theme-toggle-group ${className}` : "theme-toggle-group"}
      role="radiogroup"
    >
      {options.map((opt) => {
        const isActive = mode === opt.mode;
        return (
          <button
            aria-checked={isActive}
            className={isActive ? "theme-toggle-btn active" : "theme-toggle-btn"}
            key={opt.mode}
            onClick={() => setMode(opt.mode)}
            role="radio"
            title={opt.title}
            type="button"
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
