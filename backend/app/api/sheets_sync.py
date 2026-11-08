"""API endpoints for Google Sheets sync administration."""

from fastapi import APIRouter, Depends

from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.sheets_sync import get_sync_status, run_sync

router = APIRouter(prefix="/api/sheets-sync", tags=["sheets-sync"])


@router.get("/status")
async def sheets_sync_status(
    current_user: User = Depends(get_current_user),
):
    """Get the current Google Sheets sync status."""
    return get_sync_status()


@router.post("/trigger")
async def sheets_sync_trigger(
    current_user: User = Depends(get_current_user),
):
    """Manually trigger an immediate sync from Google Sheets."""
    result = await run_sync()
    return {
        "message": "Sync completed" if result.success else "Sync failed",
        "result": {
            "success": result.success,
            "inserted": result.inserted,
            "updated": result.updated,
            "deleted": result.deleted,
            "total_rows": result.total_rows,
            "error": result.error,
            "timestamp": result.timestamp,
        },
    }
