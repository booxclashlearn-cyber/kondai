import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { KnowledgeGraph, Source } from "../types";
import {
  Badge,
  Empty,
  Notice,
  PageHeader,
  Panel,
  type NoticeState,
} from "../components/UI";

export function KnowledgePage() {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [form, setForm] = useState({
    source_type: "billing",
    name: "",
    data: '{\n  "mrr": 0,\n  "churn_rate": 0\n}',
  });

  const load = useCallback(async () => {
    setGraph(await api.get<KnowledgeGraph>("/knowledge-graph"));
  }, []);

  useEffect(() => {
    load().catch((error) =>
      setNotice({ kind: "error", text: (error as Error).message }),
    );
  }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const data = JSON.parse(form.data) as Record<string, unknown>;
      await api.post("/sources", {
        source_type: form.source_type,
        name: form.name,
        data,
        external_id: "",
        product_id: null,
      });
      setNotice({
        kind: "success",
        text: "Business data added successfully.",
      });
      setForm({ ...form, name: "" });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    }
  }

  const facts = (graph?.nodes || []).filter(
    (node) => node.node_type === "fact",
  );

  return (
    <section className="page">
      <PageHeader
        eyebrow="Connected information"
        title="Business Data"
        description="Bring product, revenue, usage and customer information into one reliable operating view."
      />
      <Notice notice={notice} />

      <div className="knowledge-summary">
        <Panel>
          <strong>{graph?.sources.length ?? 0}</strong>
          <span>Connected sources</span>
        </Panel>
        <Panel>
          <strong>{facts.length}</strong>
          <span>Verified facts</span>
        </Panel>
        <Panel>
          <strong>{graph?.edges.length ?? 0}</strong>
          <span>Data relationships</span>
        </Panel>
      </div>

      <div className="two-column align-start">
        <Panel>
          <h3>Add a data snapshot</h3>
          <p className="muted">
            Use manual snapshots during setup. Replace them with live integrations
            when your accounts are connected.
          </p>
          <form className="form-grid" onSubmit={submit}>
            <label>
              Data type
              <select
                value={form.source_type}
                onChange={(event) =>
                  setForm({ ...form, source_type: event.target.value })
                }
              >
                {[
                  "github",
                  "database",
                  "billing",
                  "analytics",
                  "support",
                  "market",
                  "competitor",
                  "product",
                  "manual",
                ].map((type) => (
                  <option value={type} key={type}>
                    {type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Snapshot name
              <input
                required
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
              />
            </label>
            <label className="full">
              JSON data
              <textarea
                className="code-input"
                value={form.data}
                onChange={(event) =>
                  setForm({ ...form, data: event.target.value })
                }
              />
            </label>
            <button type="submit">Add business data</button>
          </form>
        </Panel>

        <div className="stack">
          <Panel>
            <div className="section-heading">
              <div>
                <span>Sources</span>
                <h3>Connected information</h3>
              </div>
            </div>
            {graph?.sources.length ? (
              <div className="source-list">
                {graph.sources.map((source: Source) => (
                  <div key={source.id}>
                    <div>
                      <strong>{source.name}</strong>
                      <p>{source.source_type}</p>
                    </div>
                    <Badge tone="good">{source.status}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <Empty>No business sources have been connected.</Empty>
            )}
          </Panel>

          <Panel>
            <div className="section-heading">
              <div>
                <span>Verified facts</span>
                <h3>What the system knows</h3>
              </div>
            </div>
            {facts.length ? (
              <div className="fact-grid">
                {facts.slice(0, 24).map((node) => (
                  <article key={node.id}>
                    <span>{node.properties.label || node.label}</span>
                    <strong>
                      {String(node.properties.value)}
                      {node.properties.unit ? ` ${node.properties.unit}` : ""}
                    </strong>
                    <small>
                      {Math.round(node.confidence * 100)}% confidence
                    </small>
                  </article>
                ))}
              </div>
            ) : (
              <Empty>Add a source to begin building your operating view.</Empty>
            )}
          </Panel>
        </div>
      </div>
    </section>
  );
}
