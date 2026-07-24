from __future__ import annotations
from typing import Any
from app.core.repository import get_repository
from app.models.schemas import GrowthAssetOutput
from app.services.audit_service import log_agent_run
from app.services.gemini_service import gemini
from app.services.knowledge_graph_service import knowledge_graph

class GrowthService:
    def __init__(self)->None:self.repo=get_repository()
    def create_campaign(self,workspace_id:str,recommendation_id:str,name:str,channel:str,audience:str,goal:str)->dict[str,Any]:
        rec=self.repo.get("recommendations",recommendation_id,workspace_id)
        if not rec:raise ValueError("Recommendation not found.")
        if rec.get("status")!="approved":raise ValueError("Approve the recommendation before execution.")
        return self.repo.create("campaigns",workspace_id,{"recommendation_id":recommendation_id,"name":name,"channel":channel,"audience":audience,"goal":goal,"status":"draft","assets_created":0,"executions":0})
    async def generate_asset(self,workspace_id:str,campaign_id:str,asset_type:str,tone:str)->dict[str,Any]:
        campaign=self.repo.get("campaigns",campaign_id,workspace_id)
        if not campaign:raise ValueError("Campaign not found.")
        rec=self.repo.get("recommendations",campaign["recommendation_id"],workspace_id);facts=knowledge_graph.verified_facts(workspace_id);grounding=[f"{n.get('properties',{}).get('label')}: {n.get('properties',{}).get('value')} {n.get('properties',{}).get('unit','')}".strip() for n in facts[:20]]
        templates={"email":f"Subject: A focused next step\n\nHi,\n\nWe are acting on a clear business priority: {rec['title']}. {rec['action']}\n\nWould you be open to a short conversation or reply so we can help?\n\nRegards,\nThe Founder","social_post":f"We are focusing on one measurable priority: {rec['title']}.\n\nWhy: {rec['reason']}\n\nWe are testing the change with real users and will share what we learn.","launch_post":f"We built this release around a verified customer and business signal: {rec['title']}.\n\n{rec['action']}","landing_page":f"Headline: {rec['title']}\n\nProblem: {rec['reason']}\n\nOutcome: {rec['expected_impact']}","blog_outline":f"Title: What we learned from {rec['title']}\n1. The signal\n2. The evidence\n3. The experiment\n4. The result\n5. What changes next","newsletter":f"This week we are focusing on {rec['title']}. The evidence suggests: {rec['reason']}. Our next action is: {rec['action']}.","release_notes":f"Improvement focus: {rec['title']}\n\nWhy it matters: {rec['reason']}\nExpected customer impact: {rec['expected_impact']}"}
        fallback={"title":f"{rec['title']} — {asset_type.replace('_',' ').title()}","content":templates.get(asset_type,rec["action"]),"call_to_action":"Review and approve this asset before publishing.","grounding_facts":grounding[:5]}
        output,metadata=await gemini.generate_structured(GrowthAssetOutput,"You are Kondai's Growth Agent. Execute approved founder strategy. Create persuasive but accurate content grounded in verified facts. Never invent capabilities, customers or results.",f"Approved recommendation:\n{rec}\nCampaign:\n{campaign}\nAsset type: {asset_type}\nTone: {tone}\nVerified facts:\n{grounding}",fallback,0.45)
        asset=self.repo.create("growth_assets",workspace_id,{"campaign_id":campaign_id,"recommendation_id":rec["id"],"asset_type":asset_type,**output.model_dump(),"status":"draft"})
        approval=self.repo.create("approvals",workspace_id,{"action_type":"publish_growth_asset","entity_type":"growth_asset","entity_id":asset["id"],"title":output.title,"content":output.content,"reason":rec["reason"],"status":"pending","revision":1,"execution_status":"not_started"})
        self.repo.update("campaigns",campaign_id,workspace_id,{"assets_created":int(campaign.get("assets_created",0))+1})
        log_agent_run(workspace_id,"growth_agent","asset_generation",f"Generated {asset_type.replace('_',' ')} for founder approval.",metadata,{"campaign_id":campaign_id,"asset_id":asset["id"],"approval_id":approval["id"]},20)
        return {"asset":asset,"approval":approval}
growth_service=GrowthService()
