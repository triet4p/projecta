import type { ApiError } from "./api/client";
import type { ConnectorRun } from "./api/generated";

export type ConnectionsLoadState =
  | "loading"
  | "ready"
  | "empty"
  | "unavailable"
  | "forbidden"
  | "not-found";

export function connectionsLoadState(
  loading: boolean,
  hasInstallations: boolean,
  error: unknown,
): ConnectionsLoadState {
  if (loading) return "loading";
  if (error !== null) {
    const code = (error as ApiError)?.problem?.code;
    if (code === "CONNECTOR_FORBIDDEN") return "forbidden";
    if (code === "CONNECTOR_NOT_FOUND") return "not-found";
    return "unavailable";
  }
  return hasInstallations ? "ready" : "empty";
}

export function connectorRunLabel(run: ConnectorRun): string {
  switch (run.state) {
    case "running":
      return "Running";
    case "succeeded":
      return "Succeeded";
    case "empty":
      return "No new events";
    case "replayed":
      return "Replayed";
    case "failed":
      return run.failureCode ? `Failed (${run.failureCode})` : "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Unavailable";
  }
}
