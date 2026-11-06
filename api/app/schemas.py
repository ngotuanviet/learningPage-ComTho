from datetime import datetime

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class StrictModel(BaseModel):
    # Unknown fields (e.g. a client trying to send "price" or "status") are rejected with 422.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str
    price: int
    list_price: int | None = None  # struck-through original price, if any
    currency: str = "VND"


class OrderCreateIn(StrictModel):
    # One of the two. product_slug is kept for older pages; product_slugs buys a bundle.
    product_slug: str | None = Field(default=None, min_length=1, max_length=200)
    product_slugs: list[str] | None = Field(default=None, min_length=1, max_length=5)
    customer_phone: str | None = Field(default=None, max_length=20)
    customer_name: str | None = Field(default=None, max_length=100)
    customer_email: EmailStr | None = None

    @field_validator("customer_phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = re.sub(r"[\s.\-()]", "", value)
        if digits.startswith("+84"):
            digits = "0" + digits[3:]
        elif digits.startswith("84") and len(digits) == 11:
            digits = "0" + digits[2:]
        if not re.fullmatch(r"0[35789]\d{8}", digits):
            raise ValueError("Số điện thoại không hợp lệ")
        return digits

    @model_validator(mode="after")
    def _one_product_field(self):
        if (self.product_slug is None) == (self.product_slugs is None):
            raise ValueError("send product_slug or product_slugs")
        if self.product_slugs is not None and any(not s or len(s) > 200 for s in self.product_slugs):
            raise ValueError("invalid product slug")
        if not self.customer_phone and not self.customer_email:
            raise ValueError("customer_phone is required")
        return self

    @property
    def slugs(self) -> list[str]:
        return self.product_slugs if self.product_slugs is not None else [self.product_slug]


class PaymentInfo(BaseModel):
    bank_code: str
    account_number: str
    account_name: str
    amount: int
    content: str  # transfer note = order code
    qr_url: str


class OrderItemOut(BaseModel):
    slug: str
    name: str
    price: int
    drive_url: str | None = None  # only once the order is paid


class OrderStatusOut(BaseModel):
    code: str
    status: str
    product_name: str
    amount: int
    expires_at: datetime
    paid_at: datetime | None = None
    # Present only while pending.
    payment: PaymentInfo | None = None
    items: list[OrderItemOut] = []
    # Present only once paid.
    drive_url: str | None = None
    email_sent: bool = False


class OrderCreatedOut(OrderStatusOut):
    # Shown once. The checkout page keeps it in sessionStorage to poll the status.
    access_token: str
