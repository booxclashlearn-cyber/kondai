from typing import Any
from app.core.repository import get_repository
def log_agent_run(workspace_id:str,agent:str,action:str,result:str,metadata:dict[str,Any],related:dict[str,Any]|None=None,estimated_minutes_saved:int=5)->dict[str,Any]:
    return get_repository().create("agent_runs",workspace_id,{"agent":agent,"action":action,"result":result,"status":"completed","metadata":metadata,"related":related or {},"estimated_minutes_saved":estimated_minutes_saved})
