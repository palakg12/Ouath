from pydantic import BaseModel
from typing import Optional

class IntegrationItem(BaseModel):
    id: str
    name: str
    type: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
