import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type {
  Approval,
  CommandCenter,
  Dashboard,
  EvidenceBundle,
  OperatingRecommendation,
} from "../types";
import {
  Badge,
  Empty,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

const ACTIVE_OPERATION_STATUSES = new Set([
  "running",
  "preparing",
  "approved_to_prepare",
]);

function confidenceLabel(value: number) {
  return `${Math.round(value * 100)}% confidence`;
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    github: "GitHub",
    firestore: "Product Database",
    stripe: "Billing",
    posthog: "Product Analytics",
    gmail: "Support Inbox",
    whatsapp: "WhatsApp",
  };
  return labels[source] || source;
}

export function TodayPage() {
  const [command, setCommand] = useState<CommandCenter | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [busy, setBusy] = useState("");
  const [showEvidence, setShowEvidence] = useState(false);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [editing, setEditing] = useState(false);
  const [revision, setRevision] = useState({
    title: "",
    action: "",
    audience: "",
    suggested_channel: "",
    success_metric: "",
  });

  const load = useCallback(async () => {
    const [commandCenter, dashboardData] = await Promise.all([
      api.get<CommandCenter>("/operations/command-center"),
      api.get<Dashboard>("/dashboard"),
    ]);
    setCommand(commandCenter);
    setDashboard(dashboardData);
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  useEffect(() => {
    const status = command?.operation_run?.status;
    if (!status || !ACTIVE_OPERATION_STATUSES.has(status)) return;
    const timer = window.setInterval(() => {
      void load();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [command?.operation_run?.status, load]);

  useEffect(() => {
    const recommendation = command?.recommendation;
    if (!recommendation) return;
    setRevision({
      title: recommendation.title,
      action: recommendation.action,
      audience: recommendation.audience,
      suggested_channel: recommendation.suggested_channel,
      success_metric: recommendation.success_metric,
    });
  }, [command?.recommendation]);

  const evidenceByKey = useMemo(
    () =>
      Object.fromEntries(
        (command?.evidence || []).map((item) => [item.key, item]),
      ) as Record<string, EvidenceBundle>,
    [command?.evidence],
  );

  async function runReview() {
    setBusy("review");
    try {
      const result = await api.post<CommandCenter>(
        "/operations/initial-review",
      );
      setCommand(result);
      setNotice({
        kind: "success",
        text: "Kondai completed a fresh review of the connected business sources.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function continueRecommendation() {
    const recommendation = command?.recommendation;
    if (!recommendation) return;
    setBusy("continue");
    try {
      const result = await api.post<CommandCenter>(
        `/operations/recommendations/${recommendation.id}/continue`,
        { founder_note: "Proceed with a controlled first version." },
      );
      setCommand(result);
      setNotice({
        kind: "success",
        text: "Kondai prepared the approved next action. Review the final work below.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function holdRecommendation() {
    const recommendation = command?.recommendation;
    if (!recommendation) return;
    setBusy("hold");
    try {
      const result = await api.post<CommandCenter>(
        `/operations/recommendations/${recommendation.id}/hold`,
        { founder_note: "Not now." },
      );
      setCommand(result);
      setNotice({ kind: "success", text: "The recommendation is on hold." });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function saveRevision(event: FormEvent) {
    event.preventDefault();
    const recommendation = command?.recommendation;
    if (!recommendation) return;
    setBusy("revise");
    try {
      const result = await api.patch<CommandCenter>(
        `/operations/recommendations/${recommendation.id}`,
        revision,
      );
      setCommand(result);
      setEditing(false);
      setNotice({
        kind: "success",
        text: "The proposed direction was updated. Kondai will use the revised version when you continue.",
      });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function approve(approval: Approval) {
    setBusy(`approve-${approval.id}`);
    try {
      await api.post(`/approvals/${approval.id}/approve`);
      setNotice({ kind: "success", text: "Final work approved." });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function execute(approval: Approval) {
    setBusy(`execute-${approval.id}`);
    try {
      await api.post(`/approvals/${approval.id}/execute`);
      setNotice({
        kind: "success",
        text: "The approved action was executed through the configured provider or internal task queue.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function refreshOutcome() {
    const plan = command?.action_plan;
    if (!plan) return;
    setBusy("outcome");
    try {
      const result = await api.post<CommandCenter>(
        `/operations/plans/${plan.id}/outcome/refresh`,
      );
      setCommand(result);
      setNotice({ kind: "success", text: "Outcome status refreshed." });
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  const readiness = command?.readiness;
  const operation = command?.operation_run;
  const review = command?.review;
  const recommendation = command?.recommendation;
  const plan = command?.action_plan;
  const counts = dashboard?.counts || {};

  return (
    <section className="page founder-command-page">
      <PageHeader
        eyebrow="Today"
        title="Your business operating view"
        description="Kondai reviews the connected product and business evidence, proposes one next action, prepares the work after permission and keeps execution under your control."
        actions={
          readiness?.ready ? (
            <button disabled={busy === "review"} onClick={runReview}>
              {busy === "review" ? "Reviewing…" : "Run a fresh review"}
            </button>
          ) : undefined
        }
      />
      <Notice notice={notice} />

      {!command ? (
        <Panel className="operating-loading">
          <div className="setup-spinner" />
          <p>Loading your operating view…</p>
        </Panel>
      ) : !readiness?.ready ? (
        <Panel className="review-readiness-card">
          <span>Initial operating review</span>
          <h3>Connect the two sources Kondai needs to begin</h3>
          <p>
            Kondai starts the first business review automatically when the
            codebase and product database are both connected.
          </p>
          <div className="required-source-grid">
            {["GitHub repository", "Product Database"].map((source) => {
              const missing = readiness?.missing_required.includes(source);
              return (
                <div className={missing ? "missing" : "complete"} key={source}>
                  <b>{missing ? "○" : "✓"}</b>
                  <div>
                    <strong>{source}</strong>
                    <span>{missing ? "Connection required" : "Connected"}</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="button-row">
            <Link className="button-link" to="/integrations">
              Open Connections
            </Link>
          </div>
        </Panel>
      ) : (
        <>
          <div className="operation-overview-grid">
            <Panel className="operation-status-card">
              <div className="operation-status-heading">
                <div>
                  <span>Current operating cycle</span>
                  <h3>{operation?.message || "Ready to review your business"}</h3>
                </div>
                <Badge
                  tone={
                    operation?.status === "failed"
                      ? "critical"
                      : operation?.status === "executed"
                        ? "good"
                        : "neutral"
                  }
                >
                  {(operation?.status || "ready").replaceAll("_", " ")}
                </Badge>
              </div>
              {operation ? (
                <div className="operation-timeline">
                  {command.operation_steps.map((step) => (
                    <div className={`operation-step ${step.status}`} key={step.id}>
                      <b>
                        {step.status === "completed"
                          ? "✓"
                          : step.status === "in_progress"
                            ? "…"
                            : "○"}
                      </b>
                      <div>
                        <strong>{step.label}</strong>
                        {step.result && <span>{step.result}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-review-state">
                  <p>
                    Your required sources are connected. Start the first review
                    to receive findings and a proposed next action.
                  </p>
                  <button disabled={busy === "review"} onClick={runReview}>
                    Review my business now
                  </button>
                </div>
              )}
            </Panel>

            <Panel className="connected-sources-card">
              <span>Evidence currently available</span>
              <div className="source-chip-list">
                {readiness.connected_sources.map((source) => (
                  <div key={source}>
                    <b>✓</b>
                    <span>{sourceLabel(source)}</span>
                  </div>
                ))}
              </div>
              {readiness.data_gaps.length > 0 && (
                <details className="data-gap-details">
                  <summary>Evidence limitations</summary>
                  <ul>
                    {readiness.data_gaps.map((gap) => (
                      <li key={gap}>{gap}</li>
                    ))}
                  </ul>
                </details>
              )}
            </Panel>
          </div>

          {review && recommendation && (
            <>
              <Panel className="founder-review-card">
                <div className="review-introduction">
                  <span>Kondai review</span>
                  <h2>{review.opening_message}</h2>
                  <p>{review.executive_summary}</p>
                </div>

                <div className="review-scope-strip">
                  {review.review_scope.map((item) => (
                    <div key={item}>
                      <b>✓</b>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                <div className="findings-heading">
                  <div>
                    <span>What I found</span>
                    <h3>Ranked findings from connected evidence</h3>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => setShowEvidence((current) => !current)}
                  >
                    {showEvidence ? "Hide evidence" : "Show evidence"}
                  </button>
                </div>

                <div className="finding-grid">
                  {command.findings.map((finding, index) => (
                    <article className="operating-finding" key={finding.id}>
                      <div className="finding-number">{index + 1}</div>
                      <div>
                        <div className="card-topline">
                          <Badge tone={finding.severity}>{finding.severity}</Badge>
                          <span>{finding.category}</span>
                        </div>
                        <h4>{finding.title}</h4>
                        <p>{finding.summary}</p>
                        <div className="why-it-matters">
                          <strong>Why it matters</strong>
                          <p>{finding.why_it_matters}</p>
                        </div>
                        {showEvidence && finding.evidence_ids.length > 0 && (
                          <div className="evidence-list">
                            {finding.evidence_ids.map((key) => {
                              const evidence = evidenceByKey[key];
                              return evidence ? (
                                <div key={key}>
                                  <span>{evidence.source_name}</span>
                                  <strong>{evidence.fact}</strong>
                                  <b>{evidence.display_value}</b>
                                </div>
                              ) : null;
                            })}
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </Panel>

              <Panel className="next-action-card">
                <div className="next-action-topline">
                  <div>
                    <span>Recommended next action</span>
                    <h2>{recommendation.title}</h2>
                  </div>
                  <div className="recommendation-badges">
                    <Badge tone="good">
                      {confidenceLabel(recommendation.confidence)}
                    </Badge>
                    <Badge tone={recommendation.risk_level}>
                      {recommendation.risk_level} risk
                    </Badge>
                  </div>
                </div>

                <div className="recommendation-content-grid">
                  <div>
                    <h4>What Kondai proposes</h4>
                    <p>{recommendation.action}</p>
                  </div>
                  <div>
                    <h4>Why this ranks first</h4>
                    <p>{recommendation.reason}</p>
                  </div>
                  <div>
                    <h4>Expected impact</h4>
                    <p>{recommendation.expected_impact}</p>
                  </div>
                  <div>
                    <h4>Success measure</h4>
                    <p>{recommendation.success_metric}</p>
                    <small>{recommendation.time_horizon}</small>
                  </div>
                </div>

                {showEvidence && recommendation.evidence_ids.length > 0 && (
                  <div className="recommendation-evidence">
                    <strong>Evidence supporting this action</strong>
                    <div className="evidence-list horizontal">
                      {recommendation.evidence_ids.map((key) => {
                        const evidence = evidenceByKey[key];
                        return evidence ? (
                          <div key={key}>
                            <span>{evidence.source_name}</span>
                            <strong>{evidence.fact}</strong>
                            <b>{evidence.display_value}</b>
                          </div>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                <button
                  className="text-button"
                  onClick={() => setShowAlternatives((current) => !current)}
                >
                  {showAlternatives ? "Hide alternatives" : "See alternatives"}
                </button>
                {showAlternatives && (
                  <div className="alternatives-box">
                    {recommendation.alternatives.map((item) => (
                      <p key={item}>{item}</p>
                    ))}
                  </div>
                )}

                {editing ? (
                  <form className="recommendation-edit-form" onSubmit={saveRevision}>
                    <label>
                      Action title
                      <input
                        value={revision.title}
                        onChange={(event) =>
                          setRevision({ ...revision, title: event.target.value })
                        }
                      />
                    </label>
                    <label className="full">
                      What Kondai should prepare
                      <textarea
                        value={revision.action}
                        onChange={(event) =>
                          setRevision({ ...revision, action: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Audience or task scope
                      <input
                        value={revision.audience}
                        onChange={(event) =>
                          setRevision({ ...revision, audience: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      Channel
                      <select
                        value={revision.suggested_channel}
                        onChange={(event) =>
                          setRevision({
                            ...revision,
                            suggested_channel: event.target.value,
                          })
                        }
                      >
                        <option value="email">Email</option>
                        <option value="social">Social</option>
                        <option value="newsletter">Newsletter</option>
                        <option value="landing_page">Landing page</option>
                        <option value="internal_task">Internal task</option>
                      </select>
                    </label>
                    <label className="full">
                      Success measure
                      <input
                        value={revision.success_metric}
                        onChange={(event) =>
                          setRevision({
                            ...revision,
                            success_metric: event.target.value,
                          })
                        }
                      />
                    </label>
                    <div className="button-row full">
                      <button disabled={busy === "revise"} type="submit">
                        Save revised direction
                      </button>
                      <button
                        className="secondary"
                        type="button"
                        onClick={() => setEditing(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : recommendation.status === "awaiting_founder" ||
                  recommendation.status === "pending" ||
                  recommendation.status === "held" ? (
                  <div className="founder-decision-panel">
                    <div>
                      <span>Founder decision</span>
                      <h3>May I continue and prepare this work?</h3>
                      <p>
                        Continuing approves the direction only. Kondai will prepare
                        the work and request final approval before execution.
                      </p>
                    </div>
                    <div className="button-row">
                      <button
                        disabled={busy === "continue"}
                        onClick={continueRecommendation}
                      >
                        {busy === "continue" ? "Preparing…" : "Continue"}
                      </button>
                      <button className="secondary" onClick={() => setEditing(true)}>
                        Change the plan
                      </button>
                      <button
                        className="quiet-button"
                        disabled={busy === "hold"}
                        onClick={holdRecommendation}
                      >
                        Not now
                      </button>
                    </div>
                  </div>
                ) : null}
              </Panel>
            </>
          )}

          {plan && (
            <Panel className="action-workspace-card">
              <div className="action-workspace-heading">
                <div>
                  <span>Work in progress</span>
                  <h2>{plan.title}</h2>
                  <p>
                    Kondai is turning the approved direction into reviewable work.
                  </p>
                </div>
                <Badge
                  tone={plan.status === "executed" ? "good" : "neutral"}
                >
                  {plan.status.replaceAll("_", " ")}
                </Badge>
              </div>

              <div className="action-progress-list">
                {command.action_steps.map((step) => (
                  <div className={`action-progress-step ${step.status}`} key={step.id}>
                    <b>{step.status === "completed" ? "✓" : "○"}</b>
                    <div>
                      <strong>{step.label}</strong>
                      {step.result && <span>{step.result}</span>}
                    </div>
                  </div>
                ))}
              </div>

              {plan.deliverables.length > 0 && (
                <div className="deliverable-grid">
                  {plan.deliverables.map((deliverable) => (
                    <div key={`${deliverable.type}-${deliverable.id}`}>
                      <span>{deliverable.type.replaceAll("_", " ")}</span>
                      <strong>{deliverable.title}</strong>
                      <Badge tone="neutral">{deliverable.status}</Badge>
                    </div>
                  ))}
                </div>
              )}

              {command.approvals.length > 0 && (
                <div className="inline-approval-list">
                  <div className="section-heading">
                    <div>
                      <span>Final review</span>
                      <h3>Approve the prepared work before execution</h3>
                    </div>
                  </div>
                  {command.approvals.map((approval) => (
                    <article className="inline-approval-card" key={approval.id}>
                      <div className="card-topline">
                        <Badge
                          tone={approval.status === "approved" ? "good" : "neutral"}
                        >
                          {approval.status}
                        </Badge>
                        <Badge
                          tone={
                            approval.execution_status === "executed"
                              ? "good"
                              : "neutral"
                          }
                        >
                          {approval.execution_status.replaceAll("_", " ")}
                        </Badge>
                      </div>
                      <h4>{approval.title}</h4>
                      <pre>{approval.content}</pre>
                      <div className="button-row">
                        {approval.status === "pending" && (
                          <button
                            disabled={busy === `approve-${approval.id}`}
                            onClick={() => approve(approval)}
                          >
                            Approve final work
                          </button>
                        )}
                        {approval.status === "approved" &&
                          approval.execution_status !== "executed" && (
                            <button
                              disabled={busy === `execute-${approval.id}`}
                              onClick={() => execute(approval)}
                            >
                              Execute approved action
                            </button>
                          )}
                        <Link className="button-link secondary-link" to="/approvals">
                          Open full approval view
                        </Link>
                      </div>
                      {approval.execution_provider && (
                        <small>
                          Execution provider: {approval.execution_provider}
                        </small>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {command.outcome && (
            <Panel className="outcome-card">
              <div>
                <span>Outcome monitoring</span>
                <h3>Here is what has happened so far</h3>
                <p>{command.outcome.latest_result}</p>
                <small>
                  Success measure: {command.outcome.success_metric} · {command.outcome.time_horizon}
                </small>
              </div>
              <button disabled={busy === "outcome"} onClick={refreshOutcome}>
                Refresh outcome
              </button>
            </Panel>
          )}

          <div className="supporting-metrics-grid">
            {[
              ["Verified facts", counts.knowledge_facts ?? 0],
              ["Pending decisions", counts.pending_recommendations ?? 0],
              ["Prepared campaigns", counts.campaigns ?? 0],
              ["Final approvals", counts.pending_approvals ?? 0],
              ["Customer issues", counts.open_support_tickets ?? 0],
            ].map(([label, value]) => (
              <Panel className="small-operating-metric" key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </Panel>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
