import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { LLMProfile, LLMProfileWrite } from "../api/generated";
import { clearCredential, settingsCanSave } from "../form-state";
import { Card, ErrorMessage, StateMessage } from "../ui";

export function SettingsScreen({ api }: { api: ProjectaApiClient }) {
  const [profile, setProfile] = useState<LLMProfile | null>(null);
  const [providerType, setProviderType] =
    useState<LLMProfileWrite["providerType"]>("openai-response");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [credential, setCredential] = useState("");
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.readLlmProfile();
      setProfile(response.profile);
      if (response.profile) {
        setProviderType(response.profile.providerType);
        setBaseUrl(response.profile.baseUrl);
        setModel(response.profile.model);
      }
    } catch (nextError) {
      setError(nextError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const payload = (): LLMProfileWrite => ({
    providerType,
    baseUrl,
    model,
    ...(credential ? { credential } : {}),
    ...(profile ? { expectedRevision: profile.revision } : {}),
  });

  const save = async (rotate: boolean) => {
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const response = rotate
        ? await api.rotateLlmCredential({ ...payload(), credential })
        : await api.writeLlmProfile(payload());
      setProfile(response.profile);
      setCredential(clearCredential());
      setNotice(
        rotate
          ? "Credential rotated. The credential field was cleared."
          : "Profile saved. The credential field was cleared.",
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!profile || !window.confirm("Remove the active LLM profile?")) return;
    setBusy(true);
    setError(null);
    try {
      await api.removeLlmProfile({ expectedRevision: profile.revision, confirm: true });
      setProfile(null);
      setCredential("");
      setNotice("Profile removed. Extraction is unavailable until a profile is configured.");
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const checkConnection = async () => {
    setChecking(true);
    setError(null);
    try {
      const result = await api.checkLlmConnection();
      setProfile((current) =>
        current
          ? {
              ...current,
              health: result.status,
              credentialConfigured: result.credentialConfigured,
              lastCheckedAt: result.checkedAt,
            }
          : current,
      );
      setNotice(`${result.status}: ${result.detail}`);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setChecking(false);
    }
  };

  if (loading) return <StateMessage kind="loading">Loading redacted runtime profile…</StateMessage>;
  return (
    <div className="screen-grid">
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Runtime configuration</p>
            <h2>LLM settings</h2>
          </div>
          {profile && <span className={`health-pill ${profile.health}`}>{profile.health}</span>}
        </div>
        <p className="muted">
          Credentials are sent only to the server and are cleared from this form after submission.
        </p>
        {error !== null && <ErrorMessage error={error} />}
        {notice && <StateMessage kind="success">{notice}</StateMessage>}
        <div className="form-grid">
          <label>
            Provider
            <select
              value={providerType}
              onChange={(event) =>
                setProviderType(event.target.value as LLMProfileWrite["providerType"])
              }
            >
              <option value="openai-response">OpenAI-compatible Responses</option>
              <option value="openai">OpenAI-compatible</option>
            </select>
          </label>
          <label>
            Base URL
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://provider.example"
            />
          </label>
          <label>
            Model
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="model-id"
            />
          </label>
          <label>
            Credential
            <input
              autoComplete="new-password"
              type="password"
              value={credential}
              onChange={(event) => setCredential(event.target.value)}
              placeholder={
                profile?.credentialConfigured
                  ? "Configured — enter to replace"
                  : "Required for extraction"
              }
            />
          </label>
        </div>
        <div className="button-row">
          <button
            disabled={busy || !settingsCanSave(profile, { baseUrl, model, credential })}
            onClick={() => void save(false)}
            type="button"
          >
            {busy ? "Saving…" : "Save profile"}
          </button>
          <button
            className="secondary"
            disabled={busy || checking || !profile || !credential}
            onClick={() => void save(true)}
            type="button"
          >
            Rotate credential
          </button>
          <button
            className="secondary"
            disabled={busy || checking || !profile}
            onClick={() => void checkConnection()}
            type="button"
          >
            {checking ? "Checking…" : "Test connection"}
          </button>
          <button
            className="danger"
            disabled={busy || !profile}
            onClick={() => void remove()}
            type="button"
          >
            Remove
          </button>
        </div>
        {profile && (
          <p className="metadata">
            Revision {profile.revision} · credential configured:{" "}
            {profile.credentialConfigured ? "yes" : "no"}
          </p>
        )}
      </Card>
    </div>
  );
}
