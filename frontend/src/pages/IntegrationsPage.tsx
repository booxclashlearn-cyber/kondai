import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type {
  Integration,
  WhatsAppEmbeddedConfig,
  WhatsAppEmbeddedSession,
} from "../types";
import {
  Badge,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

const EMPTY_FIRESTORE = {
  serviceAccount: "",
  databaseId: "(default)",
  customers: "users",
  accounts: "schools",
  subscriptions: "",
  events: "",
  documents: "",
};

type FacebookLoginResponse = {
  authResponse?: { code?: string };
  status?: string;
};

type FacebookSdk = {
  init: (options: {
    appId: string;
    cookie: boolean;
    xfbml: boolean;
    version: string;
  }) => void;
  login: (
    callback: (response: FacebookLoginResponse) => void,
    options: Record<string, unknown>,
  ) => void;
};

declare global {
  interface Window {
    FB?: FacebookSdk;
    fbAsyncInit?: () => void;
  }
}

let metaSdkPromise: Promise<void> | null = null;

function loadMetaSdk(config: WhatsAppEmbeddedConfig): Promise<void> {
  if (window.FB) {
    window.FB.init({
      appId: config.app_id,
      cookie: true,
      xfbml: false,
      version: config.graph_version,
    });
    return Promise.resolve();
  }

  if (metaSdkPromise) return metaSdkPromise;

  metaSdkPromise = new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      if (!window.FB) {
        reject(new Error("Meta JavaScript SDK did not initialise."));
        return;
      }
      window.FB.init({
        appId: config.app_id,
        cookie: true,
        xfbml: false,
        version: config.graph_version,
      });
      resolve();
    };

    const existing = document.getElementById("facebook-jssdk");
    if (existing) return;

    const script = document.createElement("script");
    script.id = "facebook-jssdk";
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    script.src = "https://connect.facebook.net/en_US/sdk.js";
    script.onerror = () => reject(new Error("Could not load the Meta login window."));
    document.body.appendChild(script);
  });

  return metaSdkPromise;
}

export function IntegrationsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [busy, setBusy] = useState("");
  const [firestoreForm, setFirestoreForm] = useState(EMPTY_FIRESTORE);
  const [stripeKey, setStripeKey] = useState("");
  const [posthogForm, setPosthogForm] = useState({
    host: "https://us.posthog.com",
    projectId: "",
    personalApiKey: "",
    activationEvent: "",
  });
  const [gmailQuery, setGmailQuery] = useState(
    "in:inbox newer_than:30d -category:promotions -category:social",
  );
  const [whatsappConfig, setWhatsappConfig] =
    useState<WhatsAppEmbeddedConfig | null>(null);

  const pendingCode = useRef<string | null>(null);
  const pendingSession = useRef<WhatsAppEmbeddedSession | null>(null);
  const completionStarted = useRef(false);

  const load = useCallback(async () => {
    setIntegrations(await api.get<Integration[]>("/integrations"));
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  useEffect(() => {
    const gmail = searchParams.get("gmail");
    const message = searchParams.get("message");
    if (gmail === "connected") {
      setNotice({
        kind: "success",
        text: "Gmail connected. Run the first inbox sync to import customer messages.",
      });
      setActive("gmail");
      setSearchParams({});
      void load();
    } else if (gmail === "error") {
      setNotice({
        kind: "error",
        text: message || "Gmail connection failed.",
      });
      setSearchParams({});
    }
  }, [load, searchParams, setSearchParams]);

  const byKey = useMemo(
    () => Object.fromEntries(integrations.map((item) => [item.key, item])),
    [integrations],
  );

  const completeWhatsApp = useCallback(async () => {
    const code = pendingCode.current;
    const session = pendingSession.current;
    if (!code || !session || completionStarted.current) return;

    completionStarted.current = true;
    setBusy("whatsapp-complete");
    try {
      const result = await api.post<Record<string, unknown>>(
        "/integrations/whatsapp/embedded/complete",
        {
          code,
          waba_id: session.waba_id,
          phone_number_id: session.phone_number_id,
          business_id: session.business_id || "",
          flow_type: session.flow_type || "embedded_signup_v4",
        },
      );
      const warning = String(result.registration_warning || "");
      setNotice({
        kind: warning ? "error" : "success",
        text: warning
          ? `WhatsApp connected, but one Meta setup step needs attention: ${warning}`
          : "WhatsApp connected. New customer chats will appear in Customer Care.",
      });
      setActive(null);
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      pendingCode.current = null;
      pendingSession.current = null;
      completionStarted.current = false;
      setBusy("");
    }
  }, [load]);

  useEffect(() => {
    const listener = (event: MessageEvent) => {
      if (
        event.origin !== "https://www.facebook.com" &&
        event.origin !== "https://web.facebook.com"
      ) {
        return;
      }

      let payload: unknown = event.data;
      if (typeof payload === "string") {
        try {
          payload = JSON.parse(payload);
        } catch {
          return;
        }
      }
      if (!payload || typeof payload !== "object") return;

      const message = payload as {
        type?: string;
        event?: string;
        data?: Record<string, unknown>;
      };
      if (message.type !== "WA_EMBEDDED_SIGNUP") return;

      if (message.event === "FINISH") {
        const data = message.data || {};
        const wabaId = String(data.waba_id || "");
        const phoneNumberId = String(data.phone_number_id || "");
        if (!wabaId || !phoneNumberId) {
          setNotice({
            kind: "error",
            text: "Meta finished the account step but did not return a phone number. Reopen the flow and complete number selection and verification.",
          });
          return;
        }
        pendingSession.current = {
          waba_id: wabaId,
          phone_number_id: phoneNumberId,
          business_id: String(data.business_id || ""),
          flow_type: "embedded_signup_v4",
        };
        void completeWhatsApp();
      } else if (message.event === "CANCEL") {
        setBusy("");
        setNotice({
          kind: "error",
          text: "WhatsApp connection was cancelled before completion.",
        });
      } else if (message.event === "ERROR") {
        setBusy("");
        setNotice({
          kind: "error",
          text: String(
            message.data?.error_message ||
              "Meta could not complete WhatsApp onboarding.",
          ),
        });
      }
    };

    window.addEventListener("message", listener);
    return () => window.removeEventListener("message", listener);
  }, [completeWhatsApp]);

  useEffect(() => {
    if (active !== "whatsapp") return;
    setBusy("whatsapp-config");
    api
      .get<WhatsAppEmbeddedConfig>(
        "/integrations/whatsapp/embedded/config",
      )
      .then(async (config) => {
        setWhatsappConfig(config);
        if (config.enabled) await loadMetaSdk(config);
      })
      .catch((error: Error) =>
        setNotice({ kind: "error", text: error.message }),
      )
      .finally(() => setBusy(""));
  }, [active]);

  async function run(
    label: string,
    action: () => Promise<unknown>,
    success: string,
  ) {
    setBusy(label);
    try {
      await action();
      setNotice({ kind: "success", text: success });
      setActive(null);
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function connectFirestore(event: FormEvent) {
    event.preventDefault();
    let serviceAccount: Record<string, unknown>;
    try {
      serviceAccount = JSON.parse(
        firestoreForm.serviceAccount,
      ) as Record<string, unknown>;
    } catch {
      setNotice({
        kind: "error",
        text: "The service account file is not valid JSON.",
      });
      return;
    }
    await run(
      "firestore",
      () =>
        api.post("/integrations/firestore/connect", {
          service_account: serviceAccount,
          database_id: firestoreForm.databaseId,
          collections: {
            customers: firestoreForm.customers,
            accounts: firestoreForm.accounts,
            subscriptions: firestoreForm.subscriptions,
            events: firestoreForm.events,
            documents: firestoreForm.documents,
          },
        }),
      "Firestore connected and customer records were indexed. Kondai has started the first operating review because the codebase and database are now available.",
    );
    setFirestoreForm(EMPTY_FIRESTORE);
  }

  async function readServiceAccount(file?: File) {
    if (!file) return;
    const text = await file.text();
    setFirestoreForm((current) => ({ ...current, serviceAccount: text }));
  }

  async function connectStripe(event: FormEvent) {
    event.preventDefault();
    await run(
      "stripe",
      () => api.post("/integrations/stripe/connect", { secret_key: stripeKey }),
      "Stripe connected and billing metrics were calculated.",
    );
    setStripeKey("");
  }

  async function connectPostHog(event: FormEvent) {
    event.preventDefault();
    await run(
      "posthog",
      () =>
        api.post("/integrations/posthog/connect", {
          host: posthogForm.host,
          project_id: posthogForm.projectId,
          personal_api_key: posthogForm.personalApiKey,
          activation_event: posthogForm.activationEvent,
        }),
      "PostHog connected and the latest usage metrics were indexed.",
    );
    setPosthogForm((current) => ({ ...current, personalApiKey: "" }));
  }

  async function connectGmail() {
    setBusy("gmail-oauth");
    try {
      const response = await api.post<{ authorization_url: string }>(
        "/integrations/gmail/oauth/start",
      );
      window.location.assign(response.authorization_url);
    } catch (error) {
      setBusy("");
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function launchWhatsAppSignup() {
    if (!whatsappConfig?.enabled) {
      setNotice({
        kind: "error",
        text: `WhatsApp onboarding is not ready. The Kondai deployment is missing: ${
          whatsappConfig?.missing_configuration.join(", ") ||
          "Meta configuration"
        }.`,
      });
      return;
    }

    try {
      setBusy("whatsapp-popup");
      await loadMetaSdk(whatsappConfig);
      if (!window.FB) throw new Error("Meta login is not available.");

      pendingCode.current = null;
      pendingSession.current = null;
      completionStarted.current = false;

      const extras: Record<string, unknown> = { sessionInfoVersion: "3" };
      if (whatsappConfig.feature_type) {
        extras.featureType = whatsappConfig.feature_type;
      }

      window.FB.login(
        (response) => {
          const code = response.authResponse?.code;
          if (!code) {
            setBusy("");
            setNotice({
              kind: "error",
              text: "Meta login closed before WhatsApp access was authorised.",
            });
            return;
          }
          pendingCode.current = code;
          void completeWhatsApp();
        },
        {
          config_id: whatsappConfig.config_id,
          response_type: "code",
          override_default_response_type: true,
          extras,
        },
      );
    } catch (error) {
      setBusy("");
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function sync(provider: string, body?: unknown) {
    await run(
      `${provider}-sync`,
      () => api.post(`/integrations/${provider}/sync`, body),
      `${
        provider === "gmail"
          ? "Support inbox"
          : provider === "whatsapp"
            ? "WhatsApp conversations"
            : provider
      } refreshed from the live service.`,
    );
  }

  async function disconnect(provider: string) {
    if (
      !window.confirm(
        "Disconnect this service? Existing historical facts will remain in the audit trail.",
      )
    ) {
      return;
    }
    await run(
      `${provider}-disconnect`,
      () => api.delete(`/integrations/${provider}`),
      "Service disconnected.",
    );
    if (provider === "github") navigate("/setup");
  }

  function summary(details: Record<string, unknown>) {
    return (details.summary || {}) as Record<string, unknown>;
  }

  function stringValue(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
  }

  const gmailConnected = Boolean(byKey.gmail?.details.connected);

  return (
    <section className="page">
      <PageHeader
        eyebrow="Connections"
        title="Connect your real business systems"
        description="Kondai marks a service connected only after authentication succeeds and live information has been read."
      />
      <Notice notice={notice} />

      <div className="integration-grid live-connectors-grid">
        {integrations.map((item) => {
          const details = item.details;
          const metrics = summary(details);
          const connected =
            Boolean(details.connected) || item.status.includes("connected");
          const lastSyncedAt = stringValue(details.last_synced_at);

          return (
            <Panel key={item.key} className="integration-card connector-card">
              <div className={`integration-icon provider-${item.key}`}>
                {item.name.charAt(0)}
              </div>
              <div className="connector-main">
                <div className="integration-title-row">
                  <h3>{item.name}</h3>
                  <Badge tone={connected ? "good" : "neutral"}>
                    {item.status.replaceAll("_", " ")}
                  </Badge>
                </div>
                <p>{item.description}</p>

                {connected && (
                  <div className="connector-metrics">
                    {item.key === "github" && (
                      <>
                        <strong>{String(details.selected_repository || "")}</strong>
                        <span>
                          {String(details.selected_branch || "default branch")}
                        </span>
                      </>
                    )}
                    {item.key === "firestore" && (
                      <>
                        <strong>{String(details.project_id || "")}</strong>
                        <span>
                          {String(metrics.total_customers || 0)} customer records ·{" "}
                          {String(metrics.total_accounts || 0)} accounts
                        </span>
                      </>
                    )}
                    {item.key === "stripe" && (
                      <>
                        <strong>
                          {String(metrics.currency || "")} {String(metrics.mrr || 0)} MRR
                        </strong>
                        <span>
                          {String(metrics.active_subscriptions || 0)} active subscriptions ·{" "}
                          {String(metrics.churn_rate || 0)}% estimated churn
                        </span>
                      </>
                    )}
                    {item.key === "posthog" && (
                      <>
                        <strong>{String(metrics.active_users || 0)} active users</strong>
                        <span>
                          {String(metrics.events_last_30_days || 0)} events in 30 days ·{" "}
                          {String(metrics.activation_rate || 0)}% activation
                        </span>
                      </>
                    )}
                    {item.key === "gmail" && (
                      <>
                        <strong>{String(details.email_address || "Gmail")}</strong>
                        <span>
                          {String(metrics.messages_imported || 0)} newly imported ·{" "}
                          {String(metrics.open_tickets || 0)} open tickets
                        </span>
                      </>
                    )}
                    {item.key === "whatsapp" && (
                      <>
                        <strong>
                          {String(details.display_phone_number || "WhatsApp Business")}
                        </strong>
                        <span>
                          {String(metrics.conversations || 0)} conversations ·{" "}
                          {String(metrics.inbound_messages || 0)} inbound messages ·{" "}
                          {String(metrics.unread_conversations || 0)} unread
                        </span>
                      </>
                    )}
                    {lastSyncedAt ? (
                      <small>
                        Last refreshed {new Date(lastSyncedAt).toLocaleString()}
                      </small>
                    ) : null}
                  </div>
                )}

                <div className="button-row">
                  {item.key === "github" ? (
                    <>
                      <button onClick={() => navigate("/setup")}>
                        Change or refresh repository
                      </button>
                      <button
                        className="danger"
                        onClick={() => disconnect("github")}
                      >
                        Disconnect
                      </button>
                    </>
                  ) : connected ? (
                    <>
                      <button
                        onClick={() =>
                          item.key === "gmail"
                            ? sync("gmail", {
                                query: gmailQuery,
                                max_messages: 100,
                              })
                            : sync(item.key)
                        }
                        disabled={busy.includes(item.key)}
                      >
                        Refresh live data
                      </button>
                      <button
                        className="secondary"
                        onClick={() => setActive(item.key)}
                      >
                        Settings
                      </button>
                      <button
                        className="danger"
                        onClick={() => disconnect(item.key)}
                      >
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() =>
                        item.key === "gmail"
                          ? connectGmail()
                          : setActive(item.key)
                      }
                    >
                      Connect {item.name}
                    </button>
                  )}
                </div>
              </div>
            </Panel>
          );
        })}
      </div>

      {active === "firestore" && (
        <Panel className="connector-form-panel">
          <div className="section-heading">
            <div>
              <span>Product database</span>
              <h3>Connect Cloud Firestore</h3>
            </div>
            <button className="secondary" onClick={() => setActive(null)}>
              Close
            </button>
          </div>
          <p className="muted">
            Upload a read-only service-account JSON file and map the collections
            Kondai should count and analyse. Raw credentials are encrypted by the
            backend.
          </p>
          <form className="form-grid" onSubmit={connectFirestore}>
            <label className="full">
              Service account JSON file
              <input
                type="file"
                accept="application/json,.json"
                onChange={(event) => readServiceAccount(event.target.files?.[0])}
              />
            </label>
            <label>
              Database ID
              <input
                value={firestoreForm.databaseId}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    databaseId: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Customers collection
              <input
                required
                value={firestoreForm.customers}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    customers: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Accounts / schools collection
              <input
                value={firestoreForm.accounts}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    accounts: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Subscriptions collection
              <input
                value={firestoreForm.subscriptions}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    subscriptions: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Product events collection
              <input
                value={firestoreForm.events}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    events: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Generated documents collection
              <input
                value={firestoreForm.documents}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    documents: event.target.value,
                  })
                }
              />
            </label>
            <details className="full secret-preview">
              <summary>Review parsed credential text</summary>
              <textarea
                className="code-input"
                value={firestoreForm.serviceAccount}
                onChange={(event) =>
                  setFirestoreForm({
                    ...firestoreForm,
                    serviceAccount: event.target.value,
                  })
                }
              />
            </details>
            <button
              disabled={busy === "firestore" || !firestoreForm.serviceAccount}
            >
              Connect and read records
            </button>
          </form>
        </Panel>
      )}

      {active === "stripe" && (
        <Panel className="connector-form-panel">
          <div className="section-heading">
            <div>
              <span>Billing</span>
              <h3>Connect Stripe</h3>
            </div>
            <button className="secondary" onClick={() => setActive(null)}>
              Close
            </button>
          </div>
          <p className="muted">Use a restricted read-only key when possible.</p>
          <form className="form-grid" onSubmit={connectStripe}>
            <label className="full">
              Stripe secret or restricted key
              <input
                type="password"
                autoComplete="off"
                required
                placeholder="rk_live_… or sk_test_…"
                value={stripeKey}
                onChange={(event) => setStripeKey(event.target.value)}
              />
            </label>
            <button disabled={busy === "stripe"}>
              Connect and calculate billing metrics
            </button>
          </form>
        </Panel>
      )}

      {active === "posthog" && (
        <Panel className="connector-form-panel">
          <div className="section-heading">
            <div>
              <span>Product analytics</span>
              <h3>Connect PostHog</h3>
            </div>
            <button className="secondary" onClick={() => setActive(null)}>
              Close
            </button>
          </div>
          <p className="muted">
            Kondai queries the previous 30 days for active users, event volume
            and activation.
          </p>
          <form className="form-grid" onSubmit={connectPostHog}>
            <label>
              PostHog host
              <input
                required
                value={posthogForm.host}
                onChange={(event) =>
                  setPosthogForm({ ...posthogForm, host: event.target.value })
                }
              />
            </label>
            <label>
              Project ID
              <input
                required
                value={posthogForm.projectId}
                onChange={(event) =>
                  setPosthogForm({
                    ...posthogForm,
                    projectId: event.target.value,
                  })
                }
              />
            </label>
            <label className="full">
              Personal API key
              <input
                type="password"
                autoComplete="off"
                required
                value={posthogForm.personalApiKey}
                onChange={(event) =>
                  setPosthogForm({
                    ...posthogForm,
                    personalApiKey: event.target.value,
                  })
                }
              />
            </label>
            <label className="full">
              Activation event
              <input
                placeholder="document_generated"
                value={posthogForm.activationEvent}
                onChange={(event) =>
                  setPosthogForm({
                    ...posthogForm,
                    activationEvent: event.target.value,
                  })
                }
              />
            </label>
            <button disabled={busy === "posthog"}>
              Connect and query analytics
            </button>
          </form>
        </Panel>
      )}

      {active === "gmail" && gmailConnected && (
        <Panel className="connector-form-panel">
          <div className="section-heading">
            <div>
              <span>Support inbox</span>
              <h3>Gmail import settings</h3>
            </div>
            <button className="secondary" onClick={() => setActive(null)}>
              Close
            </button>
          </div>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void sync("gmail", { query: gmailQuery, max_messages: 100 });
            }}
          >
            <label className="full">
              Gmail search query
              <input
                value={gmailQuery}
                onChange={(event) => setGmailQuery(event.target.value)}
              />
            </label>
            <button disabled={busy === "gmail-sync"}>
              Import matching customer emails
            </button>
          </form>
        </Panel>
      )}

      {active === "whatsapp" && (
        <Panel className="connector-form-panel whatsapp-embedded-panel">
          <div className="section-heading">
            <div>
              <span>Customer chats</span>
              <h3>Connect WhatsApp</h3>
            </div>
            <button className="secondary" onClick={() => setActive(null)}>
              Close
            </button>
          </div>

          <div className="embedded-signup-layout">
            <div>
              <h4>One guided Meta signup</h4>
              <p className="muted">
                Continue with Facebook, choose or create the business, select the
                WhatsApp number and finish verification. Kondai receives the
                technical IDs and access token automatically.
              </p>
              <div className="embedded-benefits">
                <span>✓ No access-token field</span>
                <span>✓ No Phone Number ID field</span>
                <span>✓ No WABA ID field</span>
                <span>✓ No webhook setup for each founder</span>
              </div>
            </div>

            <div className="embedded-signup-action">
              {busy === "whatsapp-config" ? (
                <p>Preparing secure WhatsApp signup…</p>
              ) : whatsappConfig?.enabled ? (
                <>
                  <button
                    className="meta-connect-button"
                    onClick={launchWhatsAppSignup}
                    disabled={busy.startsWith("whatsapp")}
                  >
                    {busy.startsWith("whatsapp")
                      ? "Completing WhatsApp connection…"
                      : "Continue with Facebook"}
                  </button>
                  <small>
                    A Meta window will open. Kondai never asks the founder to
                    copy credentials.
                  </small>
                </>
              ) : (
                <div className="platform-setup-required">
                  <strong>Platform setup required once</strong>
                  <p>
                    The Kondai owner must configure Meta Embedded Signup before
                    customers can use this button.
                  </p>
                  <code>
                    {(whatsappConfig?.missing_configuration || []).join(", ") ||
                      "Loading configuration…"}
                  </code>
                </div>
              )}
            </div>
          </div>

          {whatsappConfig?.webhook_callback_url && (
            <details className="platform-webhook-details">
              <summary>Platform owner webhook information</summary>
              <p>
                Configure this callback once in the Kondai Meta app. Customers
                do not perform this step.
              </p>
              <code>{whatsappConfig.webhook_callback_url}</code>
            </details>
          )}
        </Panel>
      )}
    </section>
  );
}
