import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Insight, IntelligenceRun, Recommendation } from "../types";
import {
  Badge,
  Empty,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

export function IntelligencePage() {
  const [runs, setRuns] = useState<IntelligenceRun[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [notice, setNotice] = useState<NoticeState>(null);

  const load = useCallback(async () => {
    const [runData, insightData, recommendationData] = await Promise.all([
      api.get<IntelligenceRun[]>("/intelligence/runs"),
      api.get<Insight[]>("/insights"),
      api.get<Recommendation[]>("/recommendations"),
    ]);
    setRuns(runData);
    setInsights(insightData);
    setRecommendations(recommendationData);
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  async function run() {
    try {
      await api.post("/intelligence/run");
      setNotice({
        kind: "success",
        text: "A new business analysis has been completed.",
      });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  async function decide(id: string, status: "approved" | "rejected") {
    try {
      await api.post(`/recommendations/${id}/decision`, {
        status,
        founder_note:
          status === "approved"
            ? "Approved for controlled execution."
            : "Not a priority right now.",
      });
      setNotice({ kind: "success", text: `Priority ${status}.` });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  const latest = runs[0];

  return (
    <section className="page">
      <PageHeader
        eyebrow="Strategy"
        title="Business Insights"
        description="Review evidence-based risks, opportunities, forecasts and recommended priorities."
        actions={<button onClick={run}>Run new analysis</button>}
      />
      <Notice notice={notice} />

      {latest ? (
        <div className="intelligence-hero">
          <Panel className="health-card">
            <span>Health score</span>
            <strong>{latest.health_score}</strong>
            <p>{latest.forecast}</p>
          </Panel>
          <Panel className="summary-card">
            <span>Executive summary</span>
            <h3>{latest.executive_summary}</h3>
          </Panel>
        </div>
      ) : (
        <Empty>Connect business data and run your first analysis.</Empty>
      )}

      <div className="two-column align-start">
        <Panel>
          <div className="section-heading">
            <div>
              <span>What changed</span>
              <h3>Insights</h3>
            </div>
          </div>
          <div className="stack">
            {insights.length ? (
              insights.map((insight) => (
                <article className="insight-card" key={insight.id}>
                  <div className="card-topline">
                    <Badge tone={insight.severity}>{insight.severity}</Badge>
                    <span>{insight.category}</span>
                  </div>
                  <h4>{insight.title}</h4>
                  <p>{insight.summary}</p>
                  <ul>
                    {insight.evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              ))
            ) : (
              <Empty>No insights are available yet.</Empty>
            )}
          </div>
        </Panel>

        <Panel>
          <div className="section-heading">
            <div>
              <span>Founder decisions</span>
              <h3>Recommended priorities</h3>
            </div>
          </div>
          <div className="stack">
            {recommendations.length ? (
              recommendations.map((item) => (
                <article className="recommendation-card" key={item.id}>
                  <div className="card-topline">
                    <Badge tone={item.priority}>{item.priority}</Badge>
                    <Badge
                      tone={item.status === "approved" ? "good" : "neutral"}
                    >
                      {item.status}
                    </Badge>
                  </div>
                  <h4>{item.title}</h4>
                  <p>{item.action}</p>
                  <div className="reason-box">
                    <strong>Why</strong>
                    <p>{item.reason}</p>
                  </div>
                  <small>
                    Confidence {Math.round(item.confidence * 100)}%
                  </small>
                  {item.status === "pending" && (
                    <div className="button-row">
                      <button onClick={() => decide(item.id, "approved")}>
                        Approve priority
                      </button>
                      <button
                        className="danger"
                        onClick={() => decide(item.id, "rejected")}
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </article>
              ))
            ) : (
              <Empty>No recommended priorities are available yet.</Empty>
            )}
          </div>
        </Panel>
      </div>
    </section>
  );
}
