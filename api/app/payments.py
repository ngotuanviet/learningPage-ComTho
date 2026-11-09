"""Match SePay bank transactions to orders.

Rules (an order becomes "paid" only here, never from the browser):
- Only incoming transfers (transferType == "in") are considered.
- Each SePay transaction id is processed once (unique provider + provider_transaction_id).
- Order code is read from the "code" field, or found in the transfer note.
- Amount must equal the order amount exactly. Otherwise the order goes to "needs_review"
  and no link is sent (refund / fix manually).
- A late but exact payment (order already expired) is accepted only within
  ORDER_LATE_GRACE_MINUTES after expiry (slow bank). Later ones go to "needs_review":
  no link, the owner checks and refunds or marks paid with the CLI.
- A second payment for an already-paid order is recorded as "needs_review" (refund manually).
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, PaymentTransaction, utcnow

log = logging.getLogger("comtho.payments")
VN_TZ = timezone(timedelta(hours=7))  # SePay sends local bank time; Vietnam has no DST


@dataclass
class Outcome:
    result: str  # matched | late_matched | duplicate | ignored | needs_review:<reason>
    newly_paid: Order | None = None


def code_candidates(code: object, content: object) -> list[str]:
    """Every substring that looks like an order code, "code" field first.

    Banks change case and glue extra text around the note, so overlapping matches are
    collected and the caller keeps the one that exists in the database.
    """
    prefix = re.escape(get_settings().order_code_prefix)
    pattern = re.compile(rf"(?=({prefix}[A-Z0-9]{{8}}))")
    found: list[str] = []
    for text in (code, content):
        if isinstance(text, str):
            for match in pattern.finditer(text.upper()):
                if match.group(1) not in found:
                    found.append(match.group(1))
    return found


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=VN_TZ)
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


class InvalidPayload(ValueError):
    pass


def lock_orders_query(codes: list[str]):
    # Order eager-loads its product with a LEFT JOIN; Postgres refuses FOR UPDATE on the
    # nullable side of an outer join, so lock only the orders table (FOR UPDATE OF orders).
    return select(Order).where(Order.code.in_(codes)).with_for_update(of=Order)


def process_sepay(db: Session, payload: dict) -> Outcome:
    tx_id = payload.get("id")
    amount = _to_int(payload.get("transferAmount"))
    if tx_id in (None, "") or amount is None:
        raise InvalidPayload("missing id or transferAmount")
    tx_id = str(tx_id)

    if payload.get("transferType") != "in":
        return Outcome("ignored")

    if db.scalar(
        select(PaymentTransaction.id).where(
            PaymentTransaction.provider == "sepay", PaymentTransaction.provider_transaction_id == tx_id
        )
    ):
        return Outcome("duplicate")

    content = str(payload.get("content") or "")
    candidates = code_candidates(payload.get("code"), content)
    order = None
    if candidates:
        # Row lock so two concurrent deliveries cannot both mark the order paid (no-op on SQLite).
        matches = db.scalars(lock_orders_query(candidates)).all()
        by_code = {o.code: o for o in matches}
        order = next((by_code[c] for c in candidates if c in by_code), None)
    code = order.code if order else (candidates[0] if candidates else None)

    now = utcnow()
    newly_paid = None
    if order is None:
        result, note = "needs_review:order_not_found", f"code={code or '-'}"
    elif order.status == "paid":
        result, note = "needs_review:already_paid", "thanh toán lần 2 cho đơn đã trả – cần hoàn tiền"
    elif order.status not in ("pending", "expired"):
        result, note = f"needs_review:order_{order.status}", None
    elif amount != order.amount:
        order.status = "needs_review"
        result, note = "needs_review:amount_mismatch", f"nhận {amount}, cần {order.amount}"
    elif order.expires_at + timedelta(minutes=get_settings().order_late_grace_minutes) < now:
        result, note = "needs_review:too_late", "trả sau khi đơn hết hạn quá lâu – kiểm tra rồi hoàn tiền hoặc mark-paid"
    else:
        late = order.status == "expired" or order.expires_at <= now
        order.status = "paid"
        order.paid_at = now
        newly_paid = order
        result, note = ("late_matched" if late else "matched"), None

    db.add(
        PaymentTransaction(
            provider="sepay",
            provider_transaction_id=tx_id,
            order_id=order.id if order else None,
            amount=amount,
            content=content[:2000],
            reference_code=(str(payload.get("referenceCode") or "") or None),
            transaction_date=_parse_date(payload.get("transactionDate")),
            status="matched" if newly_paid else "needs_review",
            note=note,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Same transaction delivered twice at the same moment: the other request won.
        db.rollback()
        return Outcome("duplicate")
    log.info("sepay tx %s -> %s (order %s)", tx_id, result, code or "-")
    return Outcome(result, newly_paid)
