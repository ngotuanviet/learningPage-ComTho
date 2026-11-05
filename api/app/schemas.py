from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    # Unknown fields (e.g. a client trying to send "price" or "status") are rejected with 422.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str
    price: int
    currency: str = "VND"


class OrderCreateIn(StrictModel):
    product_slug: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: EmailStr


class PaymentInfo(BaseModel):
    bank_code: str
    account_number: str
    account_name: str
    amount: int
    content: str  # transfer note = order code
    qr_url: str


class OrderStatusOut(BaseModel):
    code: str
    status: str
    product_name: str
    amount: int
    expires_at: datetime
    paid_at: datetime | None = None
    # Present only while pending.
    payment: PaymentInfo | None = None
    # Present only once paid.
    drive_url: str | None = None
    email_sent: bool = False


class OrderCreatedOut(OrderStatusOut):
    # Shown once. The checkout page keeps it in sessionStorage to poll the status.
    access_token: str
