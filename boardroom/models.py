from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROLES = ['CEO', 'CFO', 'CMO', 'Risk Officer']
PERSONAS = {
    'Moderator': 'Neutral chair. Frame the options fairly; expose consensus and dissent. Do not erase minority views or confuse score with probability.',
    'Researcher': 'Extract a concise fact sheet from supplied evidence only. Never invent market research, source URLs, or external verification.',
    'CEO': 'Assess strategic fit, competitive advantage, opportunity cost and long-term value. Challenge functional silos.',
    'CFO': 'Assess capital needs, NPV, payback, funding and cash flows. Use supplied calculator results exactly; challenge optimistic assumptions.',
    'CMO': 'Assess customer demand, channels, pricing, brand, market evidence and go-to-market execution.',
    'Risk Officer': 'Stress-test regulatory, operational, execution, reputational and downside assumptions. Act as devil advocate.',
}

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=1800)
    source: str = Field(min_length=1, description='Exactly one supplied source ID or assumption')

class Risk(StrictModel):
    risk: Claim
    mitigation: Claim

class AgentOutput(StrictModel):
    role: Literal['Moderator', 'Researcher', 'CEO', 'CFO', 'CMO', 'Risk Officer']
    phase: Literal['frame', 'research', 'opening', 'rebuttal', 'synthesis']
    stance: Literal['Support', 'Oppose', 'Conditional', 'Neutral']
    score: int = Field(ge=1, le=10)
    confidence: int = Field(ge=1, le=10)
    summary: Claim
    arguments: list[Claim] = Field(max_length=3)
    key_assumption: Claim
    rebuttal: Claim
    facts: list[Claim] = Field(max_length=12)
    options: list[str] = Field(max_length=8)
    recommendation: Literal['Go', 'No-go', 'Conditional-go', 'Not yet assessed']
    risks: list[Risk] = Field(max_length=5)
    dissent: list[Claim] = Field(max_length=8)
    conditions: list[Claim] = Field(max_length=8)

    @model_validator(mode='after')
    def phase_rules(self):
        if self.phase in ('opening', 'rebuttal'):
            if len(self.arguments) != 3: raise ValueError('Functional positions require exactly three arguments.')
            if self.stance == 'Neutral': raise ValueError('Functional agents must take a stance.')
        if self.phase == 'rebuttal' and len(self.rebuttal.text.split()) > 150:
            raise ValueError('Rebuttal exceeds 150 words.')
        if self.phase == 'synthesis' and (len(self.risks) != 5 or not self.conditions):
            raise ValueError('Memo requires five risks and at least one next step.')
        if self.phase == 'synthesis' and self.recommendation == 'Not yet assessed':
            raise ValueError('Synthesis requires a recommendation.')
        if self.phase == 'frame' and not self.options: raise ValueError('Framing requires decision options.')
        return self


def validate_output(raw, role, phase, sources):
    result = AgentOutput.model_validate(raw)
    if result.role != role or result.phase != phase:
        raise ValueError('Output role or phase does not match the requested task.')
    def walk(value):
        if isinstance(value, dict):
            if 'text' in value and 'source' in value and value['source'] not in sources:
                raise ValueError('Unknown source ID. Use a supplied ID or assumption.')
            for x in value.values(): walk(x)
        elif isinstance(value, list):
            for x in value: walk(x)
    walk(result.model_dump())
    return result.model_dump()
