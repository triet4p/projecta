import { useCallback, useEffect, useMemo, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type {
  ConnectorCatalogResponse,
  ConnectorInstallation,
  ConnectorRun,
} from "../api/generated";
import { connectorRunLabel, connectionsLoadState } from "../connections-state";
import { Card, ErrorMessage, StateMessage, StatusBadge, operationKey } from "../ui";

export function ConnectionsScreen({
  api,
  projectHandle,
}: {
  api: ProjectaApiClient;
  projectHandle: string;
}) {
  const [catalog, setCatalog] = useState<ConnectorCatalogResponse | null>(null);
  const [installations, setInstallations] = useState<ConnectorInstallation[]>([]);
  const [runs, setRuns] = useState<Record<string, ConnectorRun[]>>({});
  const [fixtureReference, setFixtureReference] = useState("fixture://project-a");
  const [loading, setLoading] = useState(true);
  const [busyHandle, setBusyHandle] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextCatalog, nextInstallations] = await Promise.all([
        api.getConnectorCatalog(),
        api.listConnectorInstallations(projectHandle),
      ]);
      setCatalog(nextCatalog);
      setInstallations(nextInstallations.items);
      const entries = await Promise.all(
        nextInstallations.items.map(
          async (installation) =>
            [
              installation.handle,
              (await api.listConnectorRuns(projectHandle, installation.handle)).items,
            ] as const,
        ),
      );
      setRuns(Object.fromEntries(entries));
    } catch (nextError) {
      setError(nextError);
    } finally {
      setLoading(false);
    }
  }, [api, projectHandle]);

  useEffect(() => {
    void load();
  }, [load]);

  const state = connectionsLoadState(loading, installations.length > 0, error);
  const jsonMock = useMemo(
    () => catalog?.items.find((item) => item.connectorType === "json-mock"),
    [catalog],
  );
  const jsonMockInstalled = installations.some(
    (installation) => installation.connectorType === "json-mock",
  );

  const install = async () => {
    if (!window.confirm("Install this JSON/Mock connector for the selected project?")) return;
    setBusyHandle("new");
    setError(null);
    setNotice("");
    try {
      await api.createConnectorInstallation(projectHandle, {
        fixtureReference,
        capabilities: ["inbound-import"],
      });
      setNotice("Connector installation created disabled. Enable it when ready.");
      await load();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusyHandle(null);
    }
  };

  const toggle = async (installation: ConnectorInstallation) => {
    const nextEnabled = !installation.enabled;
    if (!window.confirm(`${nextEnabled ? "Enable" : "Disable"} this connector installation?`))
      return;
    setBusyHandle(installation.handle);
    setError(null);
    setNotice("");
    try {
      await api.setConnectorInstallationEnabled(
        projectHandle,
        installation.handle,
        nextEnabled,
        installation.revision,
      );
      setNotice(`Connector ${nextEnabled ? "enabled" : "disabled"}.`);
      await load();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusyHandle(null);
    }
  };

  const run = async (installation: ConnectorInstallation) => {
    setBusyHandle(installation.handle);
    setError(null);
    setNotice("");
    try {
      const result = await api.runConnector(
        projectHandle,
        installation.handle,
        installation.revision,
        operationKey(),
      );
      setRuns((current) => ({
        ...current,
        [installation.handle]: [result, ...(current[installation.handle] ?? [])],
      }));
      setNotice(`Sync completed with state: ${connectorRunLabel(result)}.`);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusyHandle(null);
    }
  };

  const retry = async (installation: ConnectorInstallation, failed: ConnectorRun) => {
    setBusyHandle(installation.handle);
    setError(null);
    setNotice("");
    try {
      const result = await api.retryConnectorRun(
        projectHandle,
        installation.handle,
        failed.handle,
        installation.revision,
        failed.revision,
      );
      setRuns((current) => ({
        ...current,
        [installation.handle]: [result, ...(current[installation.handle] ?? [])],
      }));
      setNotice(`Retry completed with state: ${connectorRunLabel(result)}.`);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusyHandle(null);
    }
  };

  return (
    <div className="screen-grid">
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project connections</p>
            <h2>Connections</h2>
          </div>
          <span className="metadata">Scope: selected project</span>
        </div>
        <p className="muted">
          JSON/Mock is the only enabled connector in this release. Real connectors remain disabled
          until their own review and authorization boundary exists.
        </p>
        {error !== null && <ErrorMessage error={error} />}
        {notice && <StateMessage kind="success">{notice}</StateMessage>}
        {state === "loading" && (
          <StateMessage kind="loading">Loading connector catalog and installations…</StateMessage>
        )}
        {state === "forbidden" && (
          <StateMessage kind="error">Connector access is forbidden for this project.</StateMessage>
        )}
        {state === "not-found" && (
          <StateMessage kind="error">This project connection is no longer available.</StateMessage>
        )}
        {state === "unavailable" && (
          <StateMessage kind="error">
            Connector services are unavailable; no fallback data is shown.
          </StateMessage>
        )}
        {state === "empty" && (
          <StateMessage kind="empty">
            No connector installations exist for this project yet.
          </StateMessage>
        )}
        {jsonMock && !jsonMockInstalled && (
          <div className="connector-install-form">
            <label htmlFor="fixture-reference">JSON/Mock fixture reference</label>
            <input
              id="fixture-reference"
              value={fixtureReference}
              onChange={(event) => setFixtureReference(event.target.value)}
              aria-describedby="fixture-help"
            />
            <span className="metadata" id="fixture-help">
              Use a server-approved fixture:// reference. Credentials are never entered here.
            </span>
            <button disabled={busyHandle !== null} onClick={() => void install()} type="button">
              Install JSON/Mock
            </button>
          </div>
        )}
      </Card>

      {installations.length > 0 && (
        <Card>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Installed connectors</p>
              <h3>Operational status</h3>
            </div>
          </div>
          <div className="connector-table-wrap">
            <table>
              <caption className="sr-only">Connector installations and latest run status</caption>
              <thead>
                <tr>
                  <th scope="col">Connector</th>
                  <th scope="col">State</th>
                  <th scope="col">Revision</th>
                  <th scope="col">Last run</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {installations.map((installation) => {
                  const latest = runs[installation.handle]?.[0];
                  const disabled = busyHandle !== null;
                  return (
                    <tr key={installation.handle}>
                      <th scope="row">{installation.connectorType}</th>
                      <td>
                        <StatusBadge
                          status={installation.enabled ? "healthy" : "disabled"}
                          label={installation.enabled ? "Enabled" : "Disabled"}
                        />
                      </td>
                      <td>{installation.revision}</td>
                      <td>{latest ? connectorRunLabel(latest) : "Never run"}</td>
                      <td>
                        <div className="button-row compact">
                          <button
                            disabled={disabled}
                            onClick={() => void toggle(installation)}
                            type="button"
                          >
                            {installation.enabled ? "Disable" : "Enable"}
                          </button>
                          <button
                            disabled={disabled || !installation.enabled}
                            onClick={() => void run(installation)}
                            type="button"
                          >
                            Run sync
                          </button>
                          {latest?.state === "failed" && (
                            <button
                              disabled={disabled}
                              onClick={() => void retry(installation, latest)}
                              type="button"
                            >
                              Retry
                            </button>
                          )}
                        </div>
                        {latest && (
                          <span className="metadata">
                            {latest.eventCount} events · {latest.replayCount} replayed
                            {latest.deadLetterAvailable ? " · dead letter available" : ""}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
