import type { ApiError } from "./api/client";
import type { ConnectorRun } from "./api/generated";

export type ConnectionsLoadState =
  | "loading"
  | "ready"
  | "empty"
  | "unavailable"
  | "forbidden"
  | "not-found"
  | "stale";

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
    if (code === "CONNECTOR_STALE" || code === "CONNECTOR_CONFLICT") return "stale";
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
      switch (run.failureCode) {
        case "ADAPTER_CREDENTIAL_INVALID":
          return "Credential needs attention";
        case "ADAPTER_PERMISSION_DENIED":
          return "Permission needs attention";
        case "ADAPTER_RATE_LIMITED":
          return "Rate limited; try later";
        default:
          return run.failureCode ? `Failed (${run.failureCode})` : "Failed";
      }
    case "truncated":
      return "Completed with limits";
    case "cancelled":
      return "Cancelled";
    default:
      return "Unavailable";
  }
}
