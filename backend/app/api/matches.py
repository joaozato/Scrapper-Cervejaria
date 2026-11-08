from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any

from app.database import get_db
from app.models.user import User
from app.models.motorista import Motorista
from app.models.disponibilidade import Disponibilidade
from app.models.carga import Carga
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/matches", tags=["matches"])

@router.get("/provaveis")
async def get_provaveis_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # This endpoint gets all available drivers and tries to match them with available loads.
    
    # Get all drivers with disponibilidades
    disp_result = await db.execute(
        select(Disponibilidade).join(Motorista)
    )
    disponibilidades = disp_result.scalars().all()
    
    # Get all active loads
    cargas_result = await db.execute(select(Carga))
    cargas = cargas_result.scalars().all()
    
    matches = []
    
    for disp in disponibilidades:
        motorista = disp.motorista
        if not motorista.is_active:
            continue
            
        driver_matches = []
        for carga in cargas:
            # Simple match logic
            origem_match = carga.origem and disp.origem and disp.origem.lower() in carga.origem.lower()
            destino_match = carga.destino and disp.destino_preferencia and disp.destino_preferencia.lower() in carga.destino.lower()
            
            # rota_frequente match
            rota_match = False
            if motorista.rota_frequente:
                rota_parts = motorista.rota_frequente.split('-')
                if len(rota_parts) == 2:
                    ro = rota_parts[0].strip().lower()
                    rd = rota_parts[1].strip().lower()
                    if carga.origem and ro in carga.origem.lower() and carga.destino and rd in carga.destino.lower():
                        rota_match = True
            
            if (origem_match and destino_match) or rota_match:
                driver_matches.append({
                    "id": str(carga.id),
                    "load_id": carga.load_id,
                    "origem": carga.origem,
                    "destino": carga.destino,
                    "valor": float(carga.valor) if carga.valor else 0,
                    "fonte": carga.fonte,
                    "data_carregamento": carga.data_carregamento
                })
                
        if driver_matches:
            matches.append({
                "motorista_id": str(motorista.id),
                "nome": motorista.nome,
                "origem": disp.origem,
                "destino_preferencia": disp.destino_preferencia,
                "rota_frequente": motorista.rota_frequente,
                "pode_carregar_direto": disp.pode_carregar_direto,
                "cargas_sugeridas": driver_matches
            })
            
    # Mock fallback if no real matches found
    if not matches:
        matches = [
            {
                "motorista_id": "mock-1",
                "nome": "João da Silva (Mock)",
                "origem": "São Paulo - SP",
                "destino_preferencia": "Rio de Janeiro - RJ",
                "rota_frequente": "SP-RJ",
                "pode_carregar_direto": "OK",
                "cargas_sugeridas": [
                    {
                        "id": "c-mock-1",
                        "load_id": "LD-9999",
                        "origem": "Guarulhos - SP",
                        "destino": "Duque de Caxias - RJ",
                        "valor": 3500.0,
                        "fonte": "Carga Prioritária",
                        "data_carregamento": "2026-07-15"
                    }
                ]
            },
            {
                "motorista_id": "mock-2",
                "nome": "Pedro Santos (Mock)",
                "origem": "Curitiba - PR",
                "destino_preferencia": "São Paulo - SP",
                "rota_frequente": "PR-SP",
                "pode_carregar_direto": "OK",
                "cargas_sugeridas": [
                    {
                        "id": "c-mock-2",
                        "load_id": "LD-8888",
                        "origem": "São José dos Pinhais - PR",
                        "destino": "Campinas - SP",
                        "valor": 2800.0,
                        "fonte": "Pool de Cargas",
                        "data_carregamento": "2026-07-16"
                    }
                ]
            },
            {
                "motorista_id": "mock-3",
                "nome": "Lucas Oliveira (Mock)",
                "origem": "Belo Horizonte - MG",
                "destino_preferencia": "Vitória - ES",
                "rota_frequente": "MG-ES",
                "pode_carregar_direto": "NOK",
                "cargas_sugeridas": [
                    {
                        "id": "c-mock-3",
                        "load_id": "LD-7777",
                        "origem": "Betim - MG",
                        "destino": "Serra - ES",
                        "valor": 2100.0,
                        "fonte": "Carga Prioritária",
                        "data_carregamento": "2026-07-17"
                    }
                ]
            },
            {
                "motorista_id": "mock-4",
                "nome": "Marcos Costa (Mock)",
                "origem": "Goiânia - GO",
                "destino_preferencia": "Brasília - DF",
                "rota_frequente": "GO-DF",
                "pode_carregar_direto": "OK",
                "cargas_sugeridas": [
                    {
                        "id": "c-mock-4",
                        "load_id": "LD-6666",
                        "origem": "Aparecida de Goiânia - GO",
                        "destino": "Taguatinga - DF",
                        "valor": 1200.0,
                        "fonte": "Carga Prioritária",
                        "data_carregamento": "2026-07-18"
                    }
                ]
            },
            {
                "motorista_id": "mock-5",
                "nome": "André Pereira (Mock)",
                "origem": "Recife - PE",
                "destino_preferencia": "Salvador - BA",
                "rota_frequente": "PE-BA",
                "pode_carregar_direto": "OK",
                "cargas_sugeridas": [
                    {
                        "id": "c-mock-5",
                        "load_id": "LD-5555",
                        "origem": "Cabo de Santo Agostinho - PE",
                        "destino": "Camaçari - BA",
                        "valor": 4200.0,
                        "fonte": "Pool de Cargas",
                        "data_carregamento": "2026-07-19"
                    }
                ]
            }
        ]
        
    return matches
