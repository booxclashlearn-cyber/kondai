import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { AgentRun } from "../types";
import { Empty, PageHeader } from "../components/UI";

const areaLabels: Record<string, string> = {
  founder_intelligence_agent: "Business analysis",
  growth_agent: "Campaign preparation",
  support_agent: "Customer care",
  knowledge_graph: "Data processing",
  controlled_executor: "Approved execution",
  orchestrator: "Workspace operations",
  operating_review: "Business review",
  action_preparation: "Work preparation",
  outcome_tracker: "Outcome monitoring",
};

const actionLabels: Record<string, string> = {
  strategic_analysis: "Analysed business performance",
  founder_briefing: "Generated daily summary",
  founder_query: "Answered a founder question",
  source_ingestion: "Processed connected data",
  asset_generation: "Prepared campaign content",
  support_draft: "Prepared customer response",
  publish_growth_asset: "Executed approved campaign content",
  send_support_reply: "Executed approved customer response",
  initial_business_review: "Reviewed connected business evidence",
  prepare_approved_next_action: "Prepared the approved next action",
  create_internal_task: "Activated an approved internal task",
};

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) =>
    letter.toUpperCase(),
  );
}

export function ActivityPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);

  useEffect(() => {
    api.get<AgentRun[]>("/agent-activity").then(setRuns).catch(console.error);
  }, []);

  return (
    <section className="page">
      <PageHeader
        eyebrow="Operations"
        title="Activity Log"
        description="Review what the system analysed, prepared or executed, including time saved and completion status."
      />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Area</th>
              <th>Activity</th>
              <th>Result</th>
              <th>Processing mode</th>
              <th>Time saved</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>{areaLabels[run.agent] || "Workspace operations"}</td>
                <td>{actionLabels[run.action] || formatLabel(run.action)}</td>
                <td>{run.result}</td>
                <td>{String(run.metadata.mode || "standard")}</td>
                <td>{run.estimated_minutes_saved} min</td>
                <td>{new Date(run.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!runs.length && <Empty>No activity has been recorded yet.</Empty>}
      </div>
    </section>
  );
}
