import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.email import send_drive_email
from app.models import WebhookEvent, utcnow
from app.payments import InvalidPayload, process_sepay

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# SePay counts 200/201 + {"success": true} as delivered; 201 works for every webhook type.
_OK = {"success": True}


@router.post("/sepay", status_code=status.HTTP_201_CREATED)
async def sepay_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    key = get_settings().sepay_webhook_api_key
    if not key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not configured")
    if not hmac.compare_digest((authorization or "").encode(), f"Apikey {key}".encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")

    raw = await request.body()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "JSON body required") from None

    # Store the raw event first, so nothing is lost if processing fails.
    event = WebhookEvent(
        provider="sepay",
        provider_event_id=str(payload.get("id"))[:100] if payload.get("id") is not None else None,
        payload=raw.decode("utf-8", "replace")[:20000],
    )
    db.add(event)
    db.commit()

    try:
        outcome = process_sepay(db, payload)
    except InvalidPayload:
        event.result, event.processed_at = "invalid", utcnow()
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid payload") from None

    event.result, event.processed_at = outcome.result, utcnow()
    db.commit()

    # Email after the payment is committed. A failed email never fails the webhook:
    # the customer still sees the link on the checkout page, and the CLI can resend.
    order = outcome.newly_paid
    if order is not None and send_drive_email(order):
        order.email_sent_at = utcnow()
        db.commit()

    return JSONResponse(_OK, status_code=status.HTTP_201_CREATED)
