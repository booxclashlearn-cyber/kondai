import type {ReactNode} from "react";
export type NoticeState={kind:"success"|"error";text:string}|null;
export function PageHeader({eyebrow,title,description,actions}:{eyebrow:string;title:string;description:string;actions?:ReactNode}){return <header className="page-header"><div><span>{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>{actions&&<div className="header-actions">{actions}</div>}</header>}
export function Notice({notice}:{notice:NoticeState}){return notice?<div className={`notice ${notice.kind}`}>{notice.text}</div>:null}
export function Panel({children,className=""}:{children:ReactNode;className?:string}){return <section className={`panel ${className}`}>{children}</section>}
export function Empty({children}:{children:ReactNode}){return <div className="empty">{children}</div>}
export function Badge({children,tone="neutral"}:{children:ReactNode;tone?:string}){return <span className={`badge ${tone}`}>{children}</span>}
