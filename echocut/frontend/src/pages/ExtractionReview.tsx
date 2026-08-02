import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileVideo, ScrollText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import type { ExtractionContent } from "../types";

export function ExtractionReview() {
  const { id = "", versionId = "" } = useParams();
  const cache = useQueryClient();
  const project = useQuery({ queryKey: ["project", id], queryFn: () => api.project(id) });
  const assets = useQuery({ queryKey: ["assets", versionId], queryFn: () => api.assets(versionId) });
  const extraction = useQuery({ queryKey: ["extraction", versionId], queryFn: () => api.extraction(versionId), retry: false });
  const [draft, setDraft] = useState<ExtractionContent | null>(null);
  useEffect(() => { if (extraction.data) setDraft(extraction.data.content); }, [extraction.data]);
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: ["assets", versionId] }), cache.invalidateQueries({ queryKey: ["extraction", versionId] }), cache.invalidateQueries({ queryKey: ["project", id] })]); };
  const upload = useMutation({ mutationFn: ({ kind, file, duration }: { kind: "script" | "video"; file: File; duration?: number }) => api.upload(versionId, kind, file, duration), onSuccess: refresh });
  const start = useMutation({ mutationFn: () => api.startExtraction(versionId), onSuccess: refresh });
  const save = useMutation({ mutationFn: () => api.updateExtraction(versionId, draft!), onSuccess: refresh });
  const approve = useMutation({ mutationFn: () => api.approveExtraction(versionId), onSuccess: refresh });
  const version = project.data?.versions.find((item) => item.id === versionId);
  const script = assets.data?.find((item) => item.kind === "script");
  const video = assets.data?.find((item) => item.kind === "video");
  const noExtraction = extraction.error instanceof ApiError && extraction.error.status === 404;
  return <section className="max-w-7xl mx-auto px-5 py-10 space-y-6">
    <header><Link to={`/projects/${id}`} className="text-sm text-slate">← Back to project</Link><p className="eyebrow mt-5">Phase 2 · {version?.label ?? "Film version"}</p><h1 className="font-display text-5xl my-2">Extraction review</h1><p className="text-slate max-w-3xl">Upload private source media, create a typed extraction draft, correct every proposed field, then approve it before audience analysis can begin.</p></header>
    <div className="grid md:grid-cols-2 gap-5"><UploadCard kind="script" title="Screenplay PDF" icon={<ScrollText />} assetName={script?.original_name} accept="application/pdf" busy={upload.isPending} onUpload={(file) => upload.mutate({ kind: "script", file })} /><UploadCard kind="video" title="Rough cut" icon={<FileVideo />} assetName={video?.original_name} accept="video/mp4,video/quicktime" busy={upload.isPending} onUpload={(file, duration) => upload.mutate({ kind: "video", file, duration })} /></div>
    {upload.isError && <p role="alert" className="error surface p-4">{upload.error.message}</p>}
    <div className="surface p-6 flex flex-wrap justify-between items-center gap-4"><div><h2 className="font-display text-2xl m-0">Extraction job</h2><p className="text-sm text-slate mb-0">{extraction.data ? `${extraction.data.provider} · ${extraction.data.review_status}` : "Waiting for both files"}</p></div><button className="button" disabled={!script || !video || start.isPending || !!extraction.data} onClick={() => start.mutate()}>{start.isPending ? "Extracting…" : "Create extraction draft"}</button></div>
    {start.isError && <p role="alert" className="error">{start.error.message}</p>}{extraction.isError && !noExtraction && <p role="alert" className="error">Extraction could not be loaded.</p>}
    {draft && extraction.data && <ReviewEditor content={draft} approved={extraction.data.review_status === "approved"} onChange={setDraft} onSave={() => save.mutate()} onApprove={() => approve.mutate()} busy={save.isPending || approve.isPending} error={save.error?.message ?? approve.error?.message} />}
  </section>;
}

function UploadCard({ kind, title, icon, assetName, accept, busy, onUpload }: { kind: "script" | "video"; title: string; icon: React.ReactNode; assetName?: string; accept: string; busy: boolean; onUpload: (file: File, duration?: number) => void }) {
  const [file, setFile] = useState<File | null>(null); const [duration, setDuration] = useState(240);
  return <article className="surface p-6"><div className="text-gold">{icon}</div><h2 className="font-display text-2xl mb-2">{title}</h2>{assetName ? <p><CheckCircle2 size={16} className="inline text-gold" /> {assetName}</p> : <><label className="field"><span className="text-sm">Choose {title}</span><input type="file" accept={accept} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>{kind === "video" && <label className="field mt-3"><span className="text-sm">Duration in seconds (max 300)</span><input type="number" min="1" max="300" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label>}<button className="button secondary mt-4" disabled={!file || busy} onClick={() => file && onUpload(file, kind === "video" ? duration : undefined)}>Upload securely</button></>}</article>;
}

function ReviewEditor({ content, approved, onChange, onSave, onApprove, busy, error }: { content: ExtractionContent; approved: boolean; onChange: (value: ExtractionContent) => void; onSave: () => void; onApprove: () => void; busy: boolean; error?: string }) {
  const update = <K extends keyof ExtractionContent>(key: K, index: number, field: string, value: string | number) => { const list = [...content[key]] as Array<Record<string, unknown>>; list[index] = { ...list[index], [field]: value }; onChange({ ...content, [key]: list } as ExtractionContent); };
  return <div className="surface p-6 md:p-8"><div className="flex flex-wrap justify-between gap-4"><div><p className="eyebrow">Human approval gate</p><h2 className="font-display text-3xl m-0">Structured story graph</h2></div>{approved && <span><ShieldCheck className="inline text-gold" /> Approved and locked</span>}</div>{content.limitations.map((item) => <p key={item} className="text-sm text-slate border-l-2 border-gold pl-3">{item}</p>)}
    <EditorSection title="Scenes">{content.scenes.map((scene, index) => <div className="grid md:grid-cols-[120px_1fr] gap-3" key={scene.id}><label className="field"><span>Heading</span><input disabled={approved} value={scene.heading} onChange={(e) => update("scenes", index, "heading", e.target.value)} /></label><label className="field"><span>Summary</span><textarea disabled={approved} value={scene.summary} onChange={(e) => update("scenes", index, "summary", e.target.value)} /></label></div>)}</EditorSection>
    <EditorSection title="Characters">{content.characters.map((character, index) => <label className="field" key={character.id}><span>{character.id}</span><input disabled={approved} value={character.name} onChange={(e) => update("characters", index, "name", e.target.value)} /></label>)}</EditorSection>
    <EditorSection title="Story facts and reveals">{content.story_facts.map((fact, index) => <label className="field" key={fact.id}><span>{fact.fact_type} · {fact.id}</span><textarea disabled={approved} value={fact.statement} onChange={(e) => update("story_facts", index, "statement", e.target.value)} /></label>)}</EditorSection>
    <EditorSection title="Timestamped evidence">{content.evidence.map((cue, index) => <label className="field" key={cue.id}><span>{Math.floor(cue.timestamp_ms / 1000)}s · {cue.event_type}</span><textarea disabled={approved} value={cue.summary} onChange={(e) => update("evidence", index, "summary", e.target.value)} /></label>)}</EditorSection>
    {error && <p role="alert" className="error">{error}</p>}<div className="flex gap-3 mt-7"><button className="button secondary" disabled={approved || busy} onClick={onSave}>Save corrections</button><button className="button" disabled={approved || busy} onClick={onApprove}>Approve extraction</button></div></div>;
}

function EditorSection({ title, children }: { title: string; children: React.ReactNode }) { return <section className="border-t border-[#30343a] mt-6 pt-5 space-y-4"><h3 className="font-display text-2xl">{title}</h3>{children}</section>; }
