from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
