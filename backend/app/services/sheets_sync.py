"""
Google Sheets Sync Service.

Polls a public Google Sheets spreadsheet (CSV export) at a configurable
interval, compares with the database, and performs upsert/delete operations.
After each sync, broadcasts changes via WebSocket to all connected clients.
"""

import asyncio
import csv
import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.motorista import Motorista
from app.models.disponibilidade import Disponibilidade
from app.services.agents import (
    notify_dashboard_refresh,
    notify_ranking_update,
    manager,
)

logger = logging.getLogger("cargo.sheets_sync")

# Column name mapping from the spreadsheet headers to internal names.
# These are normalized (stripped, uppercased) header names.
COLUMN_MAP = {
    "MÊS": "mes",
    "DISPONÍVEL DIA": "dia_disponivel",
    "MOTORISTA/ PROPRIETÁRIO": "motorista_nome",
    "PLTS": "plts",
    "ORIGEM": "origem",
    "DESTINO PREFERÊNCIA": "destino_preferencia",
    "VALOR": "valor",
    "CADASTRO": "cadastro",
    "GR": "gr",
    "PODE CARREGAR DIRETO?": "pode_carregar_direto",
    "DATA DA CONVERSA": "data_conversa",
}


@dataclass
class SyncResult:
    """Result of a single sync operation."""

    success: bool = True
    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    total_rows: int = 0
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SyncStatus:
    """Overall sync status maintained by the service."""

    enabled: bool = True
    running: bool = False
    last_sync: Optional[SyncResult] = None
    last_hash: Optional[str] = None
    sync_count: int = 0


# Global sync status
sync_status = SyncStatus()


def _build_csv_url() -> str:
    """Build the Google Sheets CSV export URL."""
    return (
        f"https://docs.google.com/spreadsheets/d/"
        f"{settings.GOOGLE_SHEET_ID}/export?format=csv"
        f"&gid={settings.GOOGLE_SHEET_GID}"
    )


def _parse_date(date_str: str) -> datetime:
    """Parse a date string in DD/MM/YYYY format to a timezone-aware datetime."""
    date_str = date_str.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Fallback: return current time
    logger.warning(f"Could not parse date: '{date_str}', using current time")
    return datetime.now(timezone.utc)


def _parse_decimal(value_str: str) -> Decimal:
    """Parse a value string to Decimal, defaulting to 0."""
    if not value_str or not value_str.strip():
        return Decimal("0.00")
    try:
        # Handle Brazilian number format (comma as decimal separator)
        cleaned = value_str.strip().replace(".", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _parse_int(value_str: str, default: int = 0) -> int:
    """Parse an integer string with a default."""
    if not value_str or not value_str.strip():
        return default
    try:
        return int(float(value_str.strip()))
    except (ValueError, TypeError):
        return default


def _normalize_str(value: str) -> str:
    """Normalize a string value: strip and title-case."""
    return value.strip() if value else ""


def _parse_csv_rows(csv_content: str) -> list[dict]:
    """
    Parse CSV content into a list of normalized row dicts.
    Skips empty rows and the header row.
    """
    rows = []
    reader = csv.reader(io.StringIO(csv_content))

    # Find the header row (contains 'MÊS')
    header = None
    for raw_row in reader:
        stripped = [c.strip() for c in raw_row]
        if "MÊS" in stripped:
            header = stripped
            break

    if not header:
        logger.error("Could not find header row with 'MÊS' column")
        return []

    # Build column index mapping
    col_indices = {}
    for i, col_name in enumerate(header):
        if col_name in COLUMN_MAP:
            col_indices[COLUMN_MAP[col_name]] = i

    # Parse data rows
    for raw_row in reader:
        if len(raw_row) < len(col_indices):
            continue

        stripped = [c.strip() for c in raw_row]

        # Skip empty rows (no month value)
        mes_idx = col_indices.get("mes")
        if mes_idx is None or not stripped[mes_idx]:
            continue

        row = {}
        for field_name, idx in col_indices.items():
            row[field_name] = stripped[idx] if idx < len(stripped) else ""

        # Skip if essential fields are missing
        if not row.get("mes") or not row.get("motorista_nome"):
            continue

        rows.append(row)

    return rows


def _row_key(row: dict) -> tuple:
    """
    Build a composite key for a row to identify unique records.
    Uses (motorista_nome_upper, mes, dia_disponivel, origem).
    """
    return (
        row.get("motorista_nome", "").upper(),
        row.get("mes", "").upper(),
        _parse_int(row.get("dia_disponivel", "0")),
        row.get("origem", "").upper(),
    )


async def _get_or_create_motorista(
    db: AsyncSession, nome: str, cache: dict
) -> Motorista:
    """Get motorista by name (case-insensitive) or create a new one."""
    nome_upper = nome.strip().upper()

    if nome_upper in cache:
        return cache[nome_upper]

    # Try case-insensitive lookup
    result = await db.execute(
        select(Motorista).where(Motorista.nome.ilike(nome.strip()))
    )
    motorista = result.scalar_one_or_none()

    if not motorista:
        motorista = Motorista(nome=nome.strip(), tipo="motorista")
        db.add(motorista)
        await db.flush()
        logger.info(f"Created new motorista: {nome.strip()}")

    cache[nome_upper] = motorista
    return motorista


async def _sync_data(csv_content: str) -> SyncResult:
    """
    Core sync logic: parse CSV, compare with DB, upsert/delete.
    """
    result = SyncResult()

    try:
        rows = _parse_csv_rows(csv_content)
        result.total_rows = len(rows)

        if not rows:
            result.error = "No data rows found in spreadsheet"
            result.success = False
            return result

        logger.info(f"Parsed {len(rows)} rows from spreadsheet")

        async with AsyncSessionLocal() as db:
            # Build a lookup of all sheet rows by key
            sheet_lookup: dict[tuple, dict] = {}
            for row in rows:
                key = _row_key(row)
                sheet_lookup[key] = row

            # Fetch all existing disponibilidades with their motorista
            db_result = await db.execute(
                select(Disponibilidade).options()
            )
            existing_disps = db_result.scalars().all()

            # Build a lookup of existing DB records by key
            db_lookup: dict[tuple, Disponibilidade] = {}
            for disp in existing_disps:
                # We need motorista name for the key
                mot_result = await db.execute(
                    select(Motorista).where(Motorista.id == disp.motorista_id)
                )
                mot = mot_result.scalar_one_or_none()
                if mot:
                    key = (
                        mot.nome.upper(),
                        disp.mes.upper(),
                        disp.dia_disponivel,
                        disp.origem.upper(),
                    )
                    db_lookup[key] = disp

            # Motorista cache for get_or_create
            motorista_cache: dict[str, Motorista] = {}

            # Get the first admin user for updated_by
            from app.models.user import User

            admin_result = await db.execute(
                select(User).where(User.role == "admin").limit(1)
            )
            admin = admin_result.scalar_one_or_none()
            admin_id = admin.id if admin else None

            # --- INSERT / UPDATE ---
            for key, row in sheet_lookup.items():
                motorista = await _get_or_create_motorista(
                    db, row["motorista_nome"], motorista_cache
                )

                cadastro = row.get("cadastro", "NOK").upper()
                if cadastro not in ("OK", "NOK"):
                    cadastro = "NOK"

                gr = row.get("gr", "NOK").upper()
                if gr not in ("OK", "NOK"):
                    gr = "NOK"

                pode_carregar = "OK" if cadastro == "OK" and gr == "OK" else "NOK"
                dia = _parse_int(row.get("dia_disponivel", "0"))
                plts = _parse_int(row.get("plts", "25"), default=25)
                valor = _parse_decimal(row.get("valor", "0"))
                data_conversa = _parse_date(
                    row.get("data_conversa", "")
                ) if row.get("data_conversa") else datetime.now(timezone.utc)

                if key in db_lookup:
                    # UPDATE: check if anything changed
                    disp = db_lookup[key]
                    changed = False

                    if disp.plts != plts:
                        disp.plts = plts
                        changed = True
                    if disp.destino_preferencia != _normalize_str(
                        row.get("destino_preferencia", "")
                    ):
                        disp.destino_preferencia = _normalize_str(
                            row.get("destino_preferencia", "")
                        )
                        changed = True
                    if disp.valor != valor:
                        disp.valor = valor
                        changed = True
                    if disp.cadastro != cadastro:
                        disp.cadastro = cadastro
                        changed = True
                    if disp.gr != gr:
                        disp.gr = gr
                        changed = True
                    if disp.pode_carregar_direto != pode_carregar:
                        disp.pode_carregar_direto = pode_carregar
                        changed = True

                    if changed:
                        disp.updated_at = datetime.now(timezone.utc)
                        if admin_id:
                            disp.updated_by = admin_id
                        result.updated += 1
                else:
                    # INSERT
                    disp = Disponibilidade(
                        motorista_id=motorista.id,
                        mes=row.get("mes", "").upper(),
                        dia_disponivel=dia,
                        plts=plts,
                        origem=_normalize_str(row.get("origem", "")),
                        destino_preferencia=_normalize_str(
                            row.get("destino_preferencia", "")
                        ),
                        valor=valor,
                        cadastro=cadastro,
                        gr=gr,
                        pode_carregar_direto=pode_carregar,
                        data_conversa=data_conversa,
                        updated_by=admin_id,
                    )
                    db.add(disp)
                    result.inserted += 1

            # --- DELETE: records in DB but not in spreadsheet ---
            for key, disp in db_lookup.items():
                if key not in sheet_lookup:
                    await db.delete(disp)
                    result.deleted += 1

            await db.commit()

            # --- Broadcast dashboard updates if anything changed ---
            if result.inserted > 0 or result.updated > 0 or result.deleted > 0:
                logger.info(
                    f"Sync complete: +{result.inserted} ~{result.updated} "
                    f"-{result.deleted}"
                )
                await _broadcast_updates(db)
            else:
                logger.debug("Sync complete: no changes detected")

    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        result.success = False
        result.error = str(e)

    return result


async def _broadcast_updates(db: AsyncSession):
    """Broadcast dashboard, ranking, and full refresh after a sync."""
    from app.api.disponibilidades import _build_dashboard_data, _build_ranking_data

    try:
        dashboard_data = await _build_dashboard_data(db)
        await notify_dashboard_refresh(dashboard_data)

        ranking_data = await _build_ranking_data(db)
        await notify_ranking_update(ranking_data)

        # Tell frontend to refetch all disponibilidades
        await manager.broadcast({
            "type": "full_refresh",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Error broadcasting updates: {e}", exc_info=True)


async def _broadcast_sync_status():
    """Broadcast the current sync status to all connected clients."""
    status_data = {
        "enabled": sync_status.enabled,
        "running": sync_status.running,
        "sync_count": sync_status.sync_count,
    }
    if sync_status.last_sync:
        status_data["last_sync"] = {
            "success": sync_status.last_sync.success,
            "inserted": sync_status.last_sync.inserted,
            "updated": sync_status.last_sync.updated,
            "deleted": sync_status.last_sync.deleted,
            "total_rows": sync_status.last_sync.total_rows,
            "error": sync_status.last_sync.error,
            "timestamp": sync_status.last_sync.timestamp,
        }

    await manager.broadcast({
        "type": "sheets_sync_status",
        "data": status_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def run_sync() -> SyncResult:
    """
    Run a single sync cycle: fetch CSV, compare hash, sync if changed.
    This is also used by the manual trigger endpoint.
    """
    sync_status.running = True
    await _broadcast_sync_status()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(_build_csv_url())
            response.raise_for_status()
            csv_content = response.text

        # Check hash to avoid reprocessing unchanged data
        content_hash = hashlib.md5(csv_content.encode("utf-8")).hexdigest()

        if content_hash == sync_status.last_hash:
            logger.debug("Spreadsheet unchanged (same hash), skipping sync")
            result = SyncResult(
                success=True,
                total_rows=sync_status.last_sync.total_rows
                if sync_status.last_sync
                else 0,
            )
            sync_status.last_sync = result
            return result

        logger.info("Spreadsheet changed, starting sync...")
        result = await _sync_data(csv_content)

        sync_status.last_hash = content_hash
        sync_status.last_sync = result
        sync_status.sync_count += 1

        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching spreadsheet: {e}")
        result = SyncResult(success=False, error=f"HTTP {e.response.status_code}")
        sync_status.last_sync = result
        return result
    except httpx.RequestError as e:
        logger.error(f"Network error fetching spreadsheet: {e}")
        result = SyncResult(success=False, error=f"Network error: {e}")
        sync_status.last_sync = result
        return result
    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}", exc_info=True)
        result = SyncResult(success=False, error=str(e))
        sync_status.last_sync = result
        return result
    finally:
        sync_status.running = False
        await _broadcast_sync_status()


async def start_sheets_sync():
    """
    Background task: runs the sync loop at the configured interval.
    Launched from the FastAPI lifespan.
    """
    interval = settings.SHEETS_SYNC_INTERVAL_SECONDS
    logger.info(
        f"📊 Sheets sync started (interval={interval}s, "
        f"sheet={settings.GOOGLE_SHEET_ID})"
    )

    # Wait a few seconds for the app to fully start
    await asyncio.sleep(5)

    while True:
        try:
            await run_sync()
        except asyncio.CancelledError:
            logger.info("Sheets sync task cancelled")
            break
        except Exception as e:
            logger.error(f"Sync loop error: {e}", exc_info=True)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Sheets sync task cancelled during sleep")
            break


def get_sync_status() -> dict:
    """Get the current sync status as a dict (for the REST endpoint)."""
    status_data = {
        "enabled": sync_status.enabled,
        "running": sync_status.running,
        "sync_count": sync_status.sync_count,
        "interval_seconds": settings.SHEETS_SYNC_INTERVAL_SECONDS,
        "sheet_id": settings.GOOGLE_SHEET_ID,
    }
    if sync_status.last_sync:
        status_data["last_sync"] = {
            "success": sync_status.last_sync.success,
            "inserted": sync_status.last_sync.inserted,
            "updated": sync_status.last_sync.updated,
            "deleted": sync_status.last_sync.deleted,
            "total_rows": sync_status.last_sync.total_rows,
            "error": sync_status.last_sync.error,
            "timestamp": sync_status.last_sync.timestamp,
        }
    return status_data
