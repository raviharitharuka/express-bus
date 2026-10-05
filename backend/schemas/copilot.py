from pydantic import Field

from schemas.common import CamelModel


class CopilotRequest(CamelModel):
    question: str = Field(min_length=1, max_length=500)


class CopilotResponse(CamelModel):
    question: str
    answer: str
    confidence: int
    follow_ups: list[str]
