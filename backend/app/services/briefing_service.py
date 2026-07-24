from __future__ import annotations
from datetime import datetime,timezone
from typing import Any
from app.core.repository import get_repository
from app.models.schemas import BriefingOutput
from app.services.audit_service import log_agent_run
from app.services.gemini_service import gemini

class BriefingService:
    def __init__(self)->None:self.repo=get_repository()
    async def generate(self,workspace_id:str)->dict[str,Any]:
        intelligence=self.repo.list("intelligence_runs",workspace_id);latest=intelligence[0] if intelligence else None;campaigns=self.repo.list("campaigns",workspace_id);tickets=self.repo.list("support_tickets",workspace_id);approvals=self.repo.list("approvals",workspace_id);runs=self.repo.list("agent_runs",workspace_id);pending=[a for a in approvals if a.get("status")=="pending"];open_tickets=[t for t in tickets if t.get("status") in {"open","escalated"}];top_rec=latest.get("recommendations",[{}])[0].get("action","") if latest and latest.get("recommendations") else ""
        fallback={"greeting":"Good morning.","business_snapshot":[f"Business health: {latest.get('health_score',0)}/100." if latest else "Founder Intelligence has not run yet.",f"Active or draft campaigns: {len(campaigns)}.",f"Open or escalated support tickets: {len(open_tickets)}."],"top_signal":latest.get("executive_summary","Connect more business sources.") if latest else "The knowledge graph needs an intelligence run.","top_risk":latest.get("insights",[{}])[0].get("summary","No risk has been calculated.") if latest and latest.get("insights") else "No risk has been calculated.","recommendation":top_rec or "Run Founder Intelligence and approve one evidence-based action.","actions_completed":[r.get("result","") for r in runs[:3] if r.get("result")],"actions_awaiting_approval":[a.get("title","Approval required") for a in pending[:5]]}
        output,metadata=await gemini.generate_structured(BriefingOutput,"You are Kondai's Founder Briefing system. Summarise verified signals in executive language. Do not invent numbers or completed actions.",f"Latest intelligence:\n{latest}\nCampaigns:\n{campaigns[:10]}\nOpen support tickets:\n{open_tickets[:10]}\nPending approvals:\n{pending[:10]}\nRecent agent runs:\n{runs[:10]}",fallback,0.1)
        briefing=self.repo.create("briefings",workspace_id,{"date":datetime.now(timezone.utc).date().isoformat(),**output.model_dump(),"model_metadata":metadata});log_agent_run(workspace_id,"founder_intelligence_agent","founder_briefing","Generated the daily Founder Briefing.",metadata,{"briefing_id":briefing["id"]},25);return briefing
briefing_service=BriefingService()
