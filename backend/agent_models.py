"""Pydantic models for structured agent outputs with Instructor validation"""

from pydantic import BaseModel, Field
from typing import List, Optional

class EvidenceRef(BaseModel):
    source: str = Field(description="Filename or source identifier")
    excerpt: str = Field(description="Key excerpt supporting this finding", max_length=500)
    relevance: str = Field(description="Why this evidence matters")

class Finding(BaseModel):
    title: str = Field(description="Short finding title")
    description: str = Field(description="Detailed finding description")
    category: str = Field(description="e.g. legal, financial, personal, procedural")
    severity: str = Field(description="info / warning / critical")
    confidence: float = Field(ge=0.0, le=1.0, description="0-1 confidence score")
    evidence: List[EvidenceRef] = Field(description="Supporting evidence references")

class Recommendation(BaseModel):
    action: str = Field(description="Specific recommended action")
    priority: str = Field(description="high / medium / low")
    rationale: str = Field(description="Why this action is needed")
    effort: str = Field(description="low / medium / high")

class TimelineEvent(BaseModel):
    date: str = Field(description="Date or timeframe")
    event: str = Field(description="What happened")
    source: str = Field(description="Evidence source")

class Contact(BaseModel):
    name: str = Field(description="Person or organization name")
    role: str = Field(description="Their role in the case")
    priority: str = Field(description="high / medium / low")
    contact_methods: List[str] = Field(default_factory=list)

class AgentReport(BaseModel):
    agent_name: str = Field(description="Which agent produced this")
    summary: str = Field(description="Executive summary")
    findings: List[Finding] = Field(description="Key findings from analysis")
    recommendations: List[Recommendation] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    contacts: List[Contact] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


INSTRUCTOR_AVAILABLE = False
try:
    from instructor import Instructor, Mode
    from openai import OpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    pass


def create_instructor_client(api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
    """Create an Instructor client for structured LLM output."""
    if not INSTRUCTOR_AVAILABLE:
        return None
    try:
        client = Instructor(
            client=OpenAI(
                api_key=api_key,
                base_url=base_url,
            ),
            mode=Mode.JSON,
        )
        return client
    except Exception:
        return None


async def extract_structured(
    instructor_client,
    model: str,
    response_model,
    messages: list[dict],
    max_retries: int = 2,
) -> Optional[dict]:
    """Extract structured data from an LLM response using Instructor.

    Falls back gracefully if instructor is unavailable or fails.
    """
    if not instructor_client:
        return None
    try:
        result = instructor_client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=messages,
            max_retries=max_retries,
        )
        return result.model_dump()
    except Exception as e:
        import logging
        logging.getLogger("tangle.models").warning(f"Instructor extraction failed: {e}")
        return None
