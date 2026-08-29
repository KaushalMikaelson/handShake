"""Razorpay webhook endpoint.

Reads the RAW body - never a re-serialised dict - because the signature is an
HMAC over exactly the bytes Razorpay sent.

Always returns 200 for an accepted-but-duplicate delivery: a duplicate is a
successfully handled event, and returning an error would invite the gateway to
retry it forever.
"""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.payments.webhook import handle_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    result = handle_webhook(db, body=body, headers=headers)

    if not result.accepted:
        response.status_code = status.HTTP_400_BAD_REQUEST

    return {
        "status": result.status,
        "duplicate": result.duplicate,
        "detail": result.detail,
        "purchase_intent_id": result.purchase_intent_id,
    }
