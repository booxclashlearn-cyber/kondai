from app.core.repository import get_repository
from app.services.audit_service import log_agent_run

def answer_founder(workspace_id:str,instruction:str)->dict:
    repo=get_repository();intelligence=repo.list("intelligence_runs",workspace_id);briefings=repo.list("briefings",workspace_id);pending=[a for a in repo.list("approvals",workspace_id) if a.get("status")=="pending"]
    if "approval" in instruction.lower():answer=f"There are {len(pending)} pending approval(s).";action="Open Approvals and review the highest-priority outward action."
    elif intelligence:
        run=intelligence[0];answer=run.get("executive_summary","Intelligence is available.");action=run.get("recommendations",[{}])[0].get("action","Review the latest recommendations.") if run.get("recommendations") else "Review the latest recommendations."
    elif briefings:answer=briefings[0].get("top_signal","A briefing is available.");action=briefings[0].get("recommendation","Review the briefing.")
    else:answer="The knowledge graph is ready, but Founder Intelligence has not run.";action="Load or connect business sources, then run Founder Intelligence."
    log_agent_run(workspace_id,"founder_intelligence_agent","founder_query","Answered a founder question from workspace records.",{"mode":"grounded_deterministic"},{},8);return {"answer":answer,"recommended_action":action,"requires_approval":False}
