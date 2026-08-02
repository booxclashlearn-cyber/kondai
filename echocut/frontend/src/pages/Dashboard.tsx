import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Film, LockKeyhole } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Timeline } from "../components/Timeline";
import type { ReadinessStatus } from "../types";

export function Dashboard() {
  const { id = "" } = useParams();
  const cache = useQueryClient();
  const project = useQuery({ queryKey: ["project", id], queryFn: () => api.project(id), enabled: !!id });
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: api.readiness });
  const activity = useQuery({ queryKey: ["activity", id], queryFn: () => api.activity(id), enabled: !!id });
  const create = useMutation({ mutationFn: (label: "Cut A" | "Cut B") => api.createVersion(id, { label, description: "" }), onSuccess: () => { void cache.invalidateQueries({ queryKey: ["project", id] }); void cache.invalidateQueries({ queryKey: ["activity", id] }); } });
  if (project.isLoading) return <p className="max-w-7xl mx-auto p-5 text-slate">Loading project…</p>;
  if (!project.data) return <div role="alert" className="max-w-7xl mx-auto p-5">Project could not be loaded.</div>;
  const value = project.data;
  return <section className="max-w-7xl mx-auto px-5 py-10 space-y-6">
    <header><p className="eyebrow">{value.genre} · {Math.round(value.target_duration_seconds / 60)} min target</p><h1 className="font-display text-5xl mt-2 mb-3">{value.title}</h1><p className="text-slate max-w-3xl">{value.description || value.intended_audience}</p></header>
    <div className="grid lg:grid-cols-[1.4fr_.6fr] gap-6"><div className="surface p-6"><div className="flex justify-between"><h2 className="font-display text-2xl m-0">Film versions</h2>{create.isError && <span role="alert" className="error">{create.error.message}</span>}</div><div className="grid sm:grid-cols-2 gap-4 mt-5">{(["Cut A", "Cut B"] as const).map((label) => { const version = value.versions.find((item) => item.label === label); return <article key={label} className="border border-[#30343a] rounded-xl p-5"><Film className="text-gold" /><h3>{label}</h3>{version ? <><p className="text-sm text-slate">{version.description || "Ready for Phase 2 media"}</p><span className="text-xs block mb-4">Script: {version.script_status.replace("_", " ")} · Video: {version.video_status.replace("_", " ")}</span><Link className="button secondary" to={`/projects/${value.id}/versions/${version.id}/extraction`}>Open extraction review</Link></> : <><p className="text-sm text-slate">No version created.</p><button className="button secondary" onClick={() => create.mutate(label)}>Create {label}</button></>}</article>; })}</div></div>
      <div className="surface p-6"><h2 className="font-display text-2xl mt-0">Readiness</h2><div className="space-y-3">{readiness.data && Object.entries(readiness.data.services).map(([name, status]) => <div className="flex justify-between gap-3 text-sm" key={name}><span className="capitalize">{name.replaceAll("_", " ")}</span><Status value={status.status} /></div>)}{readiness.isError && <p role="alert" className="error">Readiness unavailable</p>}</div></div></div>
    <Timeline />
    <div className="grid lg:grid-cols-2 gap-6"><div className="surface p-6"><h2 className="font-display text-2xl mt-0">Workflow</h2><p className="text-sm text-slate">Uploads and extraction review are available from each cut card.</p><button className="button secondary" disabled aria-describedby="future-note"><LockKeyhole size={15} /> Run audience analysis</button><p id="future-note" className="text-xs text-slate mt-4">Audience simulation belongs to Phase 3 and remains locked until an extraction is approved.</p></div><div className="surface p-6"><h2 className="font-display text-2xl mt-0">Recent activity</h2><ol className="list-none p-0 space-y-4">{activity.data?.items.map((item) => <li key={item.id} className="flex gap-3"><FileText size={16} className="text-gold mt-1" /><div><p className="m-0 text-sm">{item.message}</p><time className="text-xs text-slate">{new Date(item.created_at).toLocaleString()}</time></div></li>)}</ol></div></div>
  </section>;
}

function Status({ value }: { value: ReadinessStatus }) {
  const icons: Record<ReadinessStatus, string> = { ready: "✓", not_configured: "○", unavailable: "!", degraded: "△" };
  return <span className="text-slate"><span aria-hidden>{icons[value]}</span> {value.replace("_", " ")}</span>;
}
