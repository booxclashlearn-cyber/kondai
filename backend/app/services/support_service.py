from __future__ import annotations
from typing import Any
from app.core.config import get_settings
from app.core.repository import get_repository
from app.models.schemas import SupportDraftOutput
from app.services.audit_service import log_agent_run
from app.services.gemini_service import gemini
from app.services.knowledge_graph_service import knowledge_graph

class SupportService:
    def __init__(self)->None:self.repo=get_repository()
    def create_ticket(self,workspace_id:str,payload:dict[str,Any])->dict[str,Any]:
        ticket=self.repo.create("support_tickets",workspace_id,{**payload,"status":"open","assigned_agent":"support_agent","draft_status":"not_started"})
        self.repo.create("feedback_items",workspace_id,{"ticket_id":ticket["id"],"type":"raw_customer_message","content":payload["message"],"status":"unclassified"});return ticket
    async def draft_answer(self,workspace_id:str,ticket_id:str)->dict[str,Any]:
        ticket=self.repo.get("support_tickets",ticket_id,workspace_id)
        if not ticket:raise ValueError("Support ticket not found.")
        facts=knowledge_graph.verified_facts(workspace_id);keywords={w.lower().strip(".,!?") for w in f"{ticket['subject']} {ticket['message']}".split() if len(w)>3};matched=[]
        for node in facts:
            label=str(node.get("properties",{}).get("label","")).lower();value=str(node.get("properties",{}).get("value","")).lower()
            if any(word in label or word in value for word in keywords):matched.append(node)
        confidence=min(0.92,0.42+len(matched)*0.1);grounding=[f"{n.get('properties',{}).get('label')}: {n.get('properties',{}).get('value')}" for n in matched[:8]];threshold=get_settings().support_confidence_threshold
        fallback={"answer":"Thank you for reporting this. I do not yet have enough verified product information to give you a reliable answer. I have escalated the ticket for confirmation." if confidence<threshold else f"Thank you for contacting us. Based on verified product information, the most relevant facts are: {'; '.join(grounding[:3])}. Please confirm whether this addresses the issue.","confidence":confidence,"grounding_facts":grounding,"escalation_reason":"Insufficient verified product evidence." if confidence<threshold else "","detected_issue_type":"bug" if "error" in ticket["message"].lower() else "question"}
        output,metadata=await gemini.generate_structured(SupportDraftOutput,"You are Kondai's Support Agent. Answer only from verified knowledge. Never invent feature behavior. Escalate when evidence is insufficient.",f"Customer ticket:\n{ticket}\nVerified matching facts:\n{grounding}",fallback,0.1)
        escalate=output.confidence<threshold or bool(output.escalation_reason);reply=self.repo.create("support_drafts",workspace_id,{"ticket_id":ticket_id,**output.model_dump(),"status":"escalated" if escalate else "draft"})
        if escalate:self.repo.update("support_tickets",ticket_id,workspace_id,{"status":"escalated","draft_status":"escalated","escalation_reason":output.escalation_reason})
        else:
            approval=self.repo.create("approvals",workspace_id,{"action_type":"send_support_reply","entity_type":"support_draft","entity_id":reply["id"],"title":f"Reply: {ticket['subject']}","content":output.answer,"reason":"Grounded support answer prepared from verified knowledge.","status":"pending","revision":1,"execution_status":"not_started"})
            self.repo.update("support_tickets",ticket_id,workspace_id,{"draft_status":"pending_approval","approval_id":approval["id"]})
        self.repo.create("feedback_items",workspace_id,{"ticket_id":ticket_id,"type":output.detected_issue_type,"content":ticket["message"],"status":"classified","confidence":output.confidence})
        log_agent_run(workspace_id,"support_agent","support_draft","Escalated ticket due to insufficient evidence." if escalate else "Prepared grounded support response for approval.",metadata,{"ticket_id":ticket_id,"support_draft_id":reply["id"]},15)
        return {"draft":reply,"escalated":escalate}
support_service=SupportService()
