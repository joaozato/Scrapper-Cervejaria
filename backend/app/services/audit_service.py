import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.models.user import User

async def log_action(
    db: AsyncSession,
    user: User,
    action: str,
    target_type: str = None,
    target_id: str = None,
    details: str = None,
):
    try:
        log = AuditLog(
            user_id=user.id if user else None,
            user_name=user.full_name if user else "Sistema",
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        db.add(log)
        # We don't commit here so it's committed alongside the main transaction
    except Exception as e:
        # Failsafe so audit logging doesn't break main flow
        print(f"Failed to write audit log: {e}")
