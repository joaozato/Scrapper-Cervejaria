from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.services.auth_service import require_admin

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("", response_model=List[AuditLogResponse])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    admin_user = Depends(require_admin), # Only admins can see this
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000)
    )
    return [AuditLogResponse.model_validate(log) for log in result.scalars().all()]
