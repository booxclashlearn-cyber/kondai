from __future__ import annotations
from typing import Any
from app.core.repository import get_repository
from app.models.schemas import IntelligenceOutput
from app.services.audit_service import log_agent_run
from app.services.gemini_service import gemini
from app.services.knowledge_graph_service import knowledge_graph

def _fact_map(facts:list[dict[str,Any]])->dict[str,Any]:
    return {node.get("properties",{}).get("label",node.get("label","")):node.get("properties",{}).get("value") for node in facts}
def _number(value:Any,default:float=0)->float:
    try:return float(value)
    except (TypeError,ValueError):return default

class FounderIntelligenceService:
    def __init__(self)->None:self.repo=get_repository()
    async def run(self,workspace_id:str)->dict[str,Any]:
        facts=knowledge_graph.verified_facts(workspace_id);metrics=_fact_map(facts)
        mrr=_number(metrics.get("Monthly recurring revenue"));churn=_number(metrics.get("Individual churn — 30 days",metrics.get("Customer churn rate",0)));retention=_number(metrics.get("Individual retention rate",metrics.get("Customer retention rate",0)));activation=_number(metrics.get("Paid individual activation",metrics.get("Activation rate",0)));active_schools=_number(metrics.get("Active paying schools"));school_target=_number(metrics.get("School growth target"));revenue_at_risk=_number(metrics.get("Revenue at risk"));dormant=_number(metrics.get("Dormant paid users"));open_tickets=_number(metrics.get("Open support tickets"));recent_commits=_number(metrics.get("Recent commits"))
        health_score=72
        health_score-=22 if churn>30 else 12 if churn>15 else 0
        health_score-=18 if activation<20 else 8 if activation<40 else 0
        if revenue_at_risk>0:health_score-=5
        if mrr>0:health_score+=4
        if recent_commits>0:health_score+=3
        health_score=max(0,min(100,health_score));insights=[];recommendations=[]
        if churn>20:
            insights.append({"title":"Churn is the strongest immediate growth constraint","category":"business","severity":"critical" if churn>40 else "high","summary":f"Measured 30-day churn is {churn:.1f}%, which weakens recurring revenue growth.","evidence":[f"30-day churn: {churn:.1f}%",f"Retention: {retention:.1f}%"]})
            recommendations.append({"title":"Launch a renewal and win-back campaign","priority":"critical" if churn>40 else "high","action":"Segment expiring and recently expired customers, ask the reason for non-renewal, and run an approved three-touch sequence.","reason":"Retention improvement is faster and cheaper than replacing every lost customer.","expected_impact":"Protect recurring revenue and reveal the main causes of non-renewal.","owner_agent":"growth_agent","confidence":0.94})
        if activation<30:
            insights.append({"title":"Paid users are not reaching the first-value milestone","category":"product","severity":"high","summary":f"Activation is {activation:.1f}%, so customers may pay without experiencing the product's core value.","evidence":[f"Paid activation: {activation:.1f}%",f"Dormant paid users: {dormant:.0f}"]})
            recommendations.append({"title":"Run a first-value activation rescue","priority":"high","action":"Guide each dormant paid user to complete one meaningful workflow and record the reason when they do not.","reason":"Users who reach value early are more likely to renew and recommend the product.","expected_impact":"Higher activation, clearer onboarding failures and improved retention.","owner_agent":"growth_agent","confidence":0.91})
        if school_target>0 and active_schools<school_target:
            gap=school_target-active_schools
            insights.append({"title":"The primary B2B growth target has a large execution gap","category":"business","severity":"high","summary":f"{active_schools:.0f} active schools are recorded against a target of {school_target:.0f}.","evidence":[f"Active paying schools: {active_schools:.0f}",f"Remaining target gap: {gap:.0f}"]})
            recommendations.append({"title":"Convert existing user clusters into school plans","priority":"high","action":"Prioritise schools with multiple existing users, book decision-maker demos and track demo-to-close conversion.","reason":"Existing user concentration creates warmer B2B opportunities than cold school acquisition.","expected_impact":"More school subscriptions and lower acquisition risk.","owner_agent":"growth_agent","confidence":0.89})
        if revenue_at_risk>0:recommendations.append({"title":"Protect revenue due for renewal","priority":"high","action":f"Assign and contact accounts representing {revenue_at_risk:.0f} in monthly value before expiry.","reason":"Revenue at risk is identifiable and time-sensitive.","expected_impact":"Higher renewal rate and lower avoidable revenue loss.","owner_agent":"growth_agent","confidence":0.95})
        if open_tickets>0:
            insights.append({"title":"Support conversations are a live product signal","category":"customer","severity":"medium","summary":f"There are {open_tickets:.0f} open support tickets that may contain objections, bugs and feature requests.","evidence":[f"Open support tickets: {open_tickets:.0f}"]})
            recommendations.append({"title":"Classify support themes and escalate product-impacting issues","priority":"medium","action":"Use the Support Agent to verify answers, group repeated complaints and feed evidence into roadmap decisions.","reason":"Customer conversations often reveal product and retention problems before aggregate analytics do.","expected_impact":"Faster resolution and a more evidence-based roadmap.","owner_agent":"support_agent","confidence":0.84})
        if not insights:
            insights.append({"title":"The system needs more connected evidence","category":"business","severity":"medium","summary":"There are not enough verified metrics to produce strong strategic conclusions.","evidence":[f"Verified knowledge facts: {len(facts)}"]})
            recommendations.append({"title":"Connect billing, analytics and support snapshots","priority":"high","action":"Add current revenue, retention, activation, feature usage and support data.","reason":"Founder Intelligence should operate from evidence rather than founder memory.","expected_impact":"More precise forecasts, risks and recommendations.","owner_agent":"founder","confidence":0.99})
        fallback={"executive_summary":f"Business health is {health_score}/100. MRR is {mrr:.0f}; churn is {churn:.1f}%; activation is {activation:.1f}%.","health_score":health_score,"forecast":"Near-term growth will remain constrained until activation and retention improve." if churn>20 or activation<30 else "Current indicators support controlled growth experiments.","insights":insights[:8],"recommendations":recommendations[:8]}
        compact=[{"label":n.get("properties",{}).get("label"),"value":n.get("properties",{}).get("value"),"unit":n.get("properties",{}).get("unit"),"confidence":n.get("confidence")} for n in facts[:120]]
        output,metadata=await gemini.generate_structured(IntelligenceOutput,"You are the Founder Intelligence Agent, an analytical AI COO. Use only verified business facts. Separate evidence from inference. Recommend strategy but do not create marketing content.",f"Verified Product Knowledge Graph facts:\n{compact}\nProduce an executive analysis and preserve numeric accuracy.",fallback,0.15)
        run=self.repo.create("intelligence_runs",workspace_id,{**output.model_dump(),"verified_fact_count":len(facts),"model_metadata":metadata})
        for insight in output.insights:self.repo.create("insights",workspace_id,{**insight.model_dump(),"intelligence_run_id":run["id"],"status":"active"})
        for rec in output.recommendations:self.repo.create("recommendations",workspace_id,{**rec.model_dump(),"intelligence_run_id":run["id"],"status":"pending","founder_note":""})
        log_agent_run(workspace_id,"founder_intelligence_agent","strategic_analysis",f"Generated {len(output.insights)} insights and {len(output.recommendations)} recommendations.",metadata,{"intelligence_run_id":run["id"]},45)
        return run
founder_intelligence=FounderIntelligenceService()
