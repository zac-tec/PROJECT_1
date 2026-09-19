"""
SCHEMAS
Every request body shape used by the API, grouped by feature. When you
add a new endpoint that needs a request body, add its model here —
keeps main.py and the routers focused on logic, not data shapes.

Material refill quantities allow decimals; mixes, bricks and labourers remain integers.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import date
from decimal import Decimal


# --------------------------- Auth ---------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# --------------------------- Admin: Rates ---------------------------
class RateUpdateRequest(BaseModel):
    new_rate: float = Field(..., gt=0)


# --------------------------- Admin: Making Charges ---------------------------
class ChargeUpdateRequest(BaseModel):
    new_value: float = Field(..., ge=0)


# --------------------------- Admin: Recipe ---------------------------
class RecipeUpdateRequest(BaseModel):
    new_qty_per_mix: float = Field(..., gt=0)


# --------------------------- Admin: Order Planning ---------------------------
class OrderRequest(BaseModel):
    order_bricks: int = Field(..., gt=0)


# --------------------------- Admin: Profit Calculator ---------------------------
class ProfitCalculatorRequest(BaseModel):
    month: Optional[str] = None                 # YYYY-MM, blank = current month
    selling_price: float = Field(..., gt=0, allow_inf_nan=False)  # explicitly supplied estimate
    bricks_sold: Optional[int] = Field(default=None, ge=0)  # optional explicit scenario
    # Optional "what-if" overrides — don't change stored settings, only affect this one calculation
    rent_override: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    manager_salary_override: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    electricity_default_override: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    water_default_override: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)


# --------------------------- Admin: Fixed Monthly Overhead ---------------------------
class FixedChargeUpdateRequest(BaseModel):
    new_value: float = Field(..., ge=0)


# --------------------------- Manager: Stock Refill ---------------------------
class StockRefillRequest(BaseModel):
    material: str
    # Decimal quantity in the material's ENTRY unit: tons for Flyash/Sand,
    # litres for Chemical, packets for Cement (converted to storage units
    # inside the endpoint, same as add_stock_refill() in the original).
    amount: float = Field(..., gt=0, le=1000000, allow_inf_nan=False)


# --------------------------- Manager: Bricks Per Mix ---------------------------
class BricksPerMixUpdateRequest(BaseModel):
    new_value: float = Field(..., gt=0)


# --------------------------- Manager: Production Entry ---------------------------
class ProductionPreviewRequest(BaseModel):
    production_date: Optional[date] = None
    mixes: Optional[int] = None
    bricks_produced: Optional[int] = None


class LabourGroup(BaseModel):
    workers: int = Field(ge=0, le=1000, strict=True)
    hours: float = Field(ge=0, le=24, allow_inf_nan=False, multiple_of=0.01)

class ProductionSaveRequest(BaseModel):
    production_date: Optional[date] = None
    labour_groups: Optional[list[LabourGroup]] = Field(default=None,max_length=100)

    @model_validator(mode='after')
    def validate_groups(self):
        from decimal import Decimal
        if self.labour_groups is not None:
            hours=sum(Decimal(str(g.hours))*g.workers for g in self.labour_groups)
            if hours!=Decimal(str(self.labour_hours)) or sum(g.workers for g in self.labour_groups)!=self.labourers:
                raise ValueError('Labour totals must match the worker/hour rows.')
        return self

    mixes: int = Field(..., ge=0)
    bricks_produced: int = Field(..., ge=0)
    calculated_field: str = "none"
    labourers: int = Field(default=0, ge=0)
    labour_hours: float = Field(..., ge=0, le=10000, allow_inf_nan=False, multiple_of=0.01)
    misc_amount: float = Field(default=0.0, ge=0)
    misc_note: str = ""
    confirm_overwrite: bool = False


# --------------------------- Manager: Utility Bills ---------------------------
class UtilityBillRequest(BaseModel):
    billing_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    bill_type: str  # "Electricity" or "Water"
    amount: float = Field(..., gt=0)
    confirm_overwrite: bool = False


# --------------------------- Admin: Client WhatsApp Number ---------------------------
class WhatsAppNumberUpdateRequest(BaseModel):
    number: str = Field(..., min_length=8)


class EmailUpdateRequest(BaseModel):
    email: str = Field(..., min_length=5)


class ScheduleUpdateRequest(BaseModel):
    send_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # "HH:MM", 24-hour
    enabled: bool


# --------------------------- Admin: Default Brick Price ---------------------------
class DefaultPriceUpdateRequest(BaseModel):
    new_value: float = Field(..., gt=0)


# --------------------------- Manager: Brick Sales ---------------------------
class BrickSaleRequest(BaseModel):
    transport_mode: Optional[Literal['none','per_brick','flat']] = None
    transport_rate: Decimal = Field(default=Decimal('0'), ge=0, max_digits=12, decimal_places=2)
    sale_date: Optional[date] = None
    customer_id: Optional[int] = Field(default=None,gt=0)
    request_id: Optional[str] = None
    customer_name: str = Field(default='',max_length=100)
    customer_mobile: str = Field(default='',max_length=30)
    @model_validator(mode='after')
    def identity(self):
        if not self.customer_id and not self.customer_name.strip() and not self.customer_mobile.strip():
            raise ValueError('Enter a customer name or phone number, or select an existing customer.')
        if self.transport_mode in (None, 'none') and self.transport_rate != 0:
            raise ValueError('Choose per-brick or total transport before entering a charge.')
        if self.transport_mode in ('per_brick', 'flat') and self.transport_rate <= 0:
            raise ValueError('Enter a transport charge greater than zero.')
        if self.request_id:
            from uuid import UUID
            self.request_id=str(UUID(self.request_id))
        return self
    bricks_purchased: int = Field(..., gt=0)
    cost_per_brick: float = Field(..., gt=0, allow_inf_nan=False)
    other_charges: float = Field(default=0.0, ge=0,allow_inf_nan=False)
    amount_paid: float = Field(..., ge=0,allow_inf_nan=False)


class StockAdjustmentRequest(BaseModel):
    kind: Literal["transfer", "return", "damage", "transfer_out"] = "transfer"
    batch_id: Optional[int] = Field(default=None, gt=0)
    change_amount: int  # positive = add stock, negative = remove stock (validated non-zero in the endpoint)
    note: str = Field(..., min_length=1)
