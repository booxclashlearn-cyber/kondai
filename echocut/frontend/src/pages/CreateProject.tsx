import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { api } from "../api";

const schema = z.object({
  title: z.string().min(1, "Film title is required").max(160),
  genre: z.string().min(2, "Genre is required").max(80),
  intended_audience: z.string().min(2, "Intended audience is required").max(240),
  target_duration_seconds: z.number().min(30, "Duration must be at least 30 seconds").max(21600),
  description: z.string().max(2000),
});
type Form = z.infer<typeof schema>;

export function CreateProject() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { description: "", target_duration_seconds: 240 } });
  const mutation = useMutation({ mutationFn: api.createProject, onSuccess: (project) => { void client.invalidateQueries({ queryKey: ["projects"] }); navigate(`/projects/${project.id}`); } });
  return <section className="max-w-2xl mx-auto px-5 py-12"><p className="eyebrow">New production</p><h1 className="font-display text-4xl">Create a film project</h1><form className="surface p-6 md:p-8 grid gap-5" onSubmit={handleSubmit((value) => mutation.mutate(value))} noValidate><Field label="Film title" error={errors.title?.message}><input {...register("title")} autoFocus /></Field><div className="grid md:grid-cols-2 gap-5"><Field label="Genre" error={errors.genre?.message}><input {...register("genre")} /></Field><Field label="Target duration (seconds)" error={errors.target_duration_seconds?.message}><input type="number" {...register("target_duration_seconds", { valueAsNumber: true })} /></Field></div><Field label="Intended audience" error={errors.intended_audience?.message}><input {...register("intended_audience")} /></Field><Field label="Project description" error={errors.description?.message}><textarea rows={5} {...register("description")} /></Field>{mutation.isError && <p role="alert" className="error">{mutation.error.message}</p>}<button className="button" disabled={mutation.isPending}>{mutation.isPending ? "Creating…" : "Create Project"}</button></form></section>;
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return <label className="field"><span className="text-sm">{label}</span>{children}{error && <span className="error" role="alert">{error}</span>}</label>;
}
