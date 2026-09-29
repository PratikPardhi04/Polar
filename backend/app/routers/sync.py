from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.sync import ConflictStatus, SyncConflict
from app.models.user import User
from app.schemas.sync import ConflictResolve, ConflictResponse, SyncBatchRequest, SyncBatchResponse
from app.services import broadcaster
from app.services.sync_service import _conflict_out, process_batch, resolve_conflict

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/events", response_model=SyncBatchResponse)
async def upload(batch: SyncBatchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response = process_batch(db, batch, actor_id=user.id)
    for alert in response.sos_alerts:
        await broadcaster.broadcast("SOS", {"incident_id": alert.incident_id, "mission_id": alert.mission_id, "personnel_id": alert.personnel_id, "escalated": alert.escalated})
    return response


@router.get("/conflicts", response_model=list[ConflictResponse])
def list_conflicts(db: Session = Depends(get_db), user: User = Depends(get_current_user), status: str = "OPEN"):
    _ = user
    q = db.query(SyncConflict)
    if status != "ALL":
        q = q.filter(SyncConflict.status == status)
    return [_conflict_out(c) for c in q.order_by(SyncConflict.created_at).all()]


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
def resolve(conflict_id: str, body: ConflictResolve, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return resolve_conflict(db, conflict_id, body.resolution, actor_id=user.id, note=body.note)
