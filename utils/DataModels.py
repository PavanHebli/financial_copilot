# Pydantic Models
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

class SQLQuery(BaseModel):
    """Structured SQL query output"""
    sql: str = Field(description="The SQL query to execute")
    explanation: str = Field(description="Brief explanation of what the query does")

class ChartMetadata(BaseModel):
    chart_type: Optional[Literal['bar', 'pie', 'line', 'scatter']]
    x_column: Optional[str]
    y_column: Optional[str]
    groupby_column: Optional[str]
    aggregation: Optional[str]
    reason: Optional[str]

class LLMResponse(BaseModel):
    text: str = Field(..., description="Mandatory textual explanation or answer")
    chart: Optional[ChartMetadata] = Field(None, description="If chart is helpful, metadata to create it; otherwise, null.")