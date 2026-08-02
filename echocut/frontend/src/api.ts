import type { Activity, Extraction, ExtractionContent, MediaAsset, Page, Project, Readiness, Version } from "./types";
const base = import.meta.env.VITE_API_URL ?? "";
export class ApiError extends Error { constructor(message:string, public status:number){super(message)} }
async function request<T>(path:string, init?:RequestInit):Promise<T>{ const isForm=init?.body instanceof FormData; const response=await fetch(`${base}${path}`,{...init,headers:{...(isForm?{}:{"Content-Type":"application/json"}),...init?.headers}}); const body=await response.json(); if(!response.ok) throw new ApiError(body.error?.message??"Request failed",response.status); return body as T; }
export const api={
 projects:()=>request<Page<Project>>("/api/v1/projects"), project:(id:string)=>request<Project>(`/api/v1/projects/${id}`),
 createProject:(data:unknown)=>request<Project>("/api/v1/projects",{method:"POST",body:JSON.stringify(data)}),
 createVersion:(id:string,data:unknown)=>request<Version>(`/api/v1/projects/${id}/versions`,{method:"POST",body:JSON.stringify(data)}),
 activity:(id:string)=>request<Page<Activity>>(`/api/v1/projects/${id}/activity`), readiness:()=>request<Readiness>("/api/v1/system/readiness"),
 assets:(versionId:string)=>request<MediaAsset[]>(`/api/v1/versions/${versionId}/uploads`),
 upload:(versionId:string,kind:"script"|"video",file:File,duration?:number)=>{const form=new FormData();form.append("file",file);if(duration)form.append("duration_seconds",String(duration));return request<MediaAsset>(`/api/v1/versions/${versionId}/uploads/${kind}`,{method:"POST",body:form})},
 extraction:(versionId:string)=>request<Extraction>(`/api/v1/versions/${versionId}/extraction`),
 startExtraction:(versionId:string)=>request<Extraction>(`/api/v1/versions/${versionId}/extract`,{method:"POST"}),
 updateExtraction:(versionId:string,content:ExtractionContent)=>request<Extraction>(`/api/v1/versions/${versionId}/extraction`,{method:"PATCH",body:JSON.stringify({content})}),
 approveExtraction:(versionId:string)=>request<Extraction>(`/api/v1/versions/${versionId}/extraction/approve`,{method:"POST"})
};
