import json
import os
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class IncidentAnalysisSchema(BaseModel):
    summary: str = Field(
        description="Short factual incident summary"
    )
    probable_root_cause: str = Field(
        description=(
            "Most likely cause supported by the supplied evidence"
        )
    )
    evidence: list[str] = Field(
        description="Evidence supporting the analysis"
    )
    recommendation: str = Field(
        description="Safe next investigation or remediation step"
    )
    confidence: str = Field(
        description="One of: low, medium, high"
    )
    manual_review_required: bool


@dataclass
class AIAnalysis:
    summary: str
    probable_root_cause: str
    evidence: list[str]
    recommendation: str
    confidence: str
    manual_review_required: bool


class GeminiIncidentAnalyst:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is missing"
            )

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

        self.client = genai.Client(
            api_key=api_key
        )

    def analyze(
        self,
        incident_data: dict,
    ) -> AIAnalysis:
        prompt = self._build_prompt(
            incident_data
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=IncidentAnalysisSchema,
                system_instruction=(
                    "You are an infrastructure incident analyst. "
                    "Analyze only the supplied operational evidence. "
                    "Do not invent missing facts. "
                    "Do not execute or propose destructive commands. "
                    "Clearly state when evidence is insufficient."
                ),
            ),
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response"
            )

        parsed = IncidentAnalysisSchema.model_validate_json(
            response.text
        )

        return AIAnalysis(
            summary=parsed.summary,
            probable_root_cause=(
                parsed.probable_root_cause
            ),
            evidence=parsed.evidence,
            recommendation=parsed.recommendation,
            confidence=parsed.confidence,
            manual_review_required=(
                parsed.manual_review_required
            ),
        )

    @staticmethod
    def _build_prompt(
        incident_data: dict,
    ) -> str:
        return f"""
Analyze this infrastructure incident.

Incident data:
{json.dumps(incident_data, indent=2)}

Your responsibilities:

1. Summarize what failed.
2. Identify the most probable cause using only the evidence.
3. List the evidence supporting the conclusion.
4. Recommend a safe next action.
5. Mark manual_review_required as true when:
   - evidence is incomplete;
   - the database or Redis is affected;
   - CPU or memory usage is abnormal;
   - automatic remediation already failed.
"""