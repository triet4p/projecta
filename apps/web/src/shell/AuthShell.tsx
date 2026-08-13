import { type ReactNode, useEffect, useState } from "react";

import type { AuthSession, ProjectaApiClient } from "../api/client";
import { ApiError } from "../api/client";
import { Card, StateMessage } from "../ui";

export function AuthShell({ api, children }: { api: ProjectaApiClient; children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api
      .getAuthSession()
      .then(setSession)
      .catch((error: unknown) => {
        // A 401 is the expected unauthenticated browser state in production;
        // other failures remain visible instead of becoming local fallback.
        if (error instanceof ApiError && error.problem.status === 401) {
          setSession({ requestId: error.problem.requestId, authenticated: false });
        } else {
          setSession({ requestId: "auth-unavailable", authenticated: false });
        }
      })
      .finally(() => setLoading(false));
  }, [api]);

  if (loading) return <StateMessage kind="loading">Checking your Projecta session…</StateMessage>;
  if (!session?.authenticated) {
    return (
      <main className="auth-gate">
        <Card>
          <p className="eyebrow">Projecta</p>
          <h1>Sign in to continue</h1>
          <p className="muted">
            Project access is established by the server after identity verification.
          </p>
          <a
            className="auth-button"
            href={`/auth/login?returnTo=${encodeURIComponent(window.location.pathname)}`}
          >
            Sign in
          </a>
        </Card>
      </main>
    );
  }

  return (
    <>
      <div className="auth-session-bar" role="status">
        <span>Signed in</span>
        <button
          className="secondary"
          onClick={() => {
            void api.logout().finally(() => window.location.assign("/"));
          }}
          type="button"
        >
          Sign out
        </button>
      </div>
      {children}
    </>
  );
}
