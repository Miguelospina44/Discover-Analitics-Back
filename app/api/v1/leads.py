"""Flujo PÚBLICO de captura de leads.

A diferencia del resto de la API (analítica anónima, autenticada por cuenta),
este endpoint es público y guarda PII: nombre, teléfono, fecha de nacimiento y
correo de un visitante antes de redirigirlo a Discover.

NOTA DE PRIVACIDAD (producción): antes de usar esto con datos reales hay que
añadir consentimiento explícito, retención y manejo de habeas data. Aquí es
solo un flujo de prueba con datos ficticios; se mantiene deliberadamente
separado de las tablas de analítica anónima.
"""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.v1.schemas import LeadCaptureResponse, LeadCreate
from app.infra.orm import Lead

# Destino al que se redirige el navegador tras capturar el lead. Placeholder del
# sitio de Discover; el frontend hace la redirección real con este valor.
DISCOVER_REDIRECT_URL = "https://discover-co.com"

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadCaptureResponse, status_code=201)
async def create_lead(body: LeadCreate, session: DbSession) -> LeadCaptureResponse:
    lead = Lead(
        name=body.name,
        phone=body.phone,
        birth_date=body.birth_date,
        email=str(body.email),
        source=body.source,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return LeadCaptureResponse(id=lead.id, redirect_url=DISCOVER_REDIRECT_URL)
