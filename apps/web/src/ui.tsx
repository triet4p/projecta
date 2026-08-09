import type { ReactNode } from "react";

import { ApiError } from "./api/client";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Toolbar({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`toolbar ${className}`}>{children}</div>;
}

export function Breadcrumbs({ children }: { children: ReactNode }) {
  return (
    <nav aria-label="Breadcrumb" className="metadata">
      {children}
    </nav>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state-message empty">
      <strong>{title}</strong>
      <div>{children}</div>
      {action}
    </div>
  );
}

export function Skeleton({ count = 3 }: { count?: number }) {
  return (
    <div aria-label="Loading" aria-live="polite" className="result-stack" role="status">
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton" key={index} />
      ))}
    </div>
  );
}

export function StatusBadge({ status, label = status }: { status: string; label?: string }) {
  return <span className={`status-badge ${status}`}>{label}</span>;
}

export function StateMessage({
  kind,
  children,
}: {
  kind: "loading" | "empty" | "error" | "success";
  children: ReactNode;
}) {
  return (
    <div
      aria-live={kind === "error" ? "assertive" : "polite"}
      className={`state-message ${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

export function ErrorMessage({ error }: { error: unknown }) {
  return <StateMessage kind="error">{apiErrorMessage(error)}</StateMessage>;
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.problem.detail} Request ID: ${error.problem.requestId}`;
  }
  if (error instanceof Error) return error.message;
  return "The request could not be completed safely.";
}

export function operationKey(): string {
  return crypto.randomUUID();
}

export function redactInternal(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactInternal);
  if (typeof value !== "object" || value === null) return value;
  const result: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (/iri|graph|storage|endpoint|secret|authorization/i.test(key)) continue;
    result[key] = redactInternal(item);
  }
  return result;
}

export function SafeJson({ value }: { value: unknown }) {
  return <pre className="safe-json">{JSON.stringify(redactInternal(value), null, 2)}</pre>;
}
