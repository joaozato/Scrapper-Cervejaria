from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.motorista import Motorista
from app.models.user import User
from app.schemas.motorista import MotoristaCreate, MotoristaUpdate, MotoristaResponse
from app.services.auth_service import get_current_user, require_admin
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/motoristas", tags=["motoristas"])


@router.get("", response_model=List[MotoristaResponse])
@router.get("/", response_model=List[MotoristaResponse], include_in_schema=False)
async def list_motoristas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Motorista).order_by(Motorista.nome)
    )
    return [MotoristaResponse.model_validate(m) for m in result.scalars().all()]


@router.get("/{motorista_id}", response_model=MotoristaResponse)
async def get_motorista(
    motorista_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Motorista).where(Motorista.id == motorista_id)
    )
    motorista = result.scalar_one_or_none()
    if not motorista:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")
    return MotoristaResponse.model_validate(motorista)


@router.post("", response_model=MotoristaResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=MotoristaResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_motorista(
    data: MotoristaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if exists
    result = await db.execute(
        select(Motorista).where(Motorista.nome == data.nome)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Motorista já cadastrado",
        )

    motorista = Motorista(nome=data.nome, tipo=data.tipo)
    db.add(motorista)
    await log_action(db, current_user, "CREATE_MOTORISTA", "motorista", str(motorista.id), f"Criou motorista {motorista.nome}")
    await db.commit()
    await db.refresh(motorista)
    return MotoristaResponse.model_validate(motorista)


@router.put("/{motorista_id}", response_model=MotoristaResponse)
async def update_motorista(
    motorista_id: UUID,
    data: MotoristaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Motorista).where(Motorista.id == motorista_id)
    )
    motorista = result.scalar_one_or_none()
    if not motorista:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(motorista, key, value)

    await log_action(db, current_user, "UPDATE_MOTORISTA", "motorista", str(motorista.id), f"Atualizou motorista {motorista.nome}")
    await db.commit()
    await db.refresh(motorista)
    return MotoristaResponse.model_validate(motorista)


@router.delete("/{motorista_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_motorista(
    motorista_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(Motorista).where(Motorista.id == motorista_id)
    )
    motorista = result.scalar_one_or_none()
    if not motorista:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")

    # LGPD Compliance: Soft-delete / Anonymization
    old_name = motorista.nome
    motorista.nome = f"Motorista Anônimo ({str(motorista.id)[:8]})"
    motorista.is_active = False
    
    await log_action(db, current_user, "DELETE_MOTORISTA", "motorista", str(motorista.id), f"Excluiu (anonimizou) motorista {old_name}")
    await db.commit()
    await db.refresh(motorista)
