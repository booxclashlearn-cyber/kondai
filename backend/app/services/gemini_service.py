from __future__ import annotations
import asyncio,json,time
from typing import Any,TypeVar
from pydantic import BaseModel
from app.core.config import get_settings
T=TypeVar("T",bound=BaseModel)
class GeminiService:
    def __init__(self)->None:self.settings=get_settings();self._client:Any=None
    @property
    def enabled(self)->bool:return self.settings.ai_mode.lower()=="vertex" and bool(self.settings.google_cloud_project)
    def _get_client(self)->Any:
        if self._client is None:
            from google import genai
            self._client=genai.Client(vertexai=True,project=self.settings.google_cloud_project,location=self.settings.google_cloud_location)
        return self._client
    async def generate_structured(self,output_model:type[T],system_instruction:str,prompt:str,fallback:dict[str,Any],temperature:float=0.2)->tuple[T,dict[str,Any]]:
        if not self.enabled:return output_model.model_validate(fallback),{"mode":"deterministic","model":"deterministic-grounded","input_tokens":0,"output_tokens":0,"latency_ms":0}
        started=time.perf_counter()
        def run()->Any:
            from google.genai import types
            return self._get_client().models.generate_content(model=self.settings.gemini_model,contents=prompt,config=types.GenerateContentConfig(system_instruction=system_instruction,temperature=temperature,response_mime_type="application/json",response_json_schema=output_model.model_json_schema()))
        try:
            response=await asyncio.wait_for(asyncio.to_thread(run),timeout=60);parsed=getattr(response,"parsed",None) or json.loads(response.text or "{}");result=output_model.model_validate(parsed);usage=getattr(response,"usage_metadata",None)
            return result,{"mode":"vertex","model":self.settings.gemini_model,"input_tokens":getattr(usage,"prompt_token_count",0) if usage else 0,"output_tokens":getattr(usage,"candidates_token_count",0) if usage else 0,"latency_ms":round((time.perf_counter()-started)*1000)}
        except Exception as exc:return output_model.model_validate(fallback),{"mode":"fallback_after_error","model":self.settings.gemini_model,"input_tokens":0,"output_tokens":0,"latency_ms":round((time.perf_counter()-started)*1000),"error":str(exc)}
gemini=GeminiService()
