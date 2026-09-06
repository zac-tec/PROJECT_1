"""
SCHEMAS
Every request body shape used by the API, grouped by feature. When you
add a new endpoint that needs a request body, add its model here —
keeps main.py and the routers focused on logic, not data shapes.

Rule: quantities (stock, mixes, bricks, labourers) are always int.
Only rates, charges, and money amounts (misc_expense, utility bills,
selling price) are allowed to be float.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


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
    selling_price: Optional[float] = None        # blank = use default_cost_per_brick setting (7.50)
    bricks_sold: Optional[int] = None             # blank = defaults to production total
    # Optional "what-if" overrides — don't change stored settings, only affect this one calculation
    rent_override: Optional[float] = None
    manager_salary_override: Optional[float] = None
    electricity_default_override: Optional[float] = None
    water_default_override: Optional[float] = None


# --------------------------- Admin: Fixed Monthly Overhead ---------------------------
class FixedChargeUpdateRequest(BaseModel):
    new_value: float = Field(..., ge=0)


# --------------------------- Manager: Stock Refill ---------------------------
class StockRefillRequest(BaseModel):
    material: str
    # Whole number in the material's ENTRY unit: tons for Flyash/Sand,
    # litres for Chemical, packets for Cement (converted to storage units
    # inside the endpoint, same as add_stock_refill() in the original).
    amount: int = Field(..., gt=0)


# --------------------------- Manager: Bricks Per Mix ---------------------------
class BricksPerMixUpdateRequest(BaseModel):
    new_value: float = Field(..., gt=0)


# --------------------------- Manager: Production Entry ---------------------------
class ProductionPreviewRequest(BaseModel):
    mixes: Optional[int] = None
    bricks_produced: Optional[int] = None


class ProductionSaveRequest(BaseModel):
    mixes: int = Field(..., ge=0)
    bricks_produced: int = Field(..., ge=0)
    calculated_field: str = "none"
    labourers: int = Field(..., ge=0)
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
    customer_name: str = Field(..., min_length=1)
    customer_mobile: str = Field(..., min_length=1)
    bricks_purchased: int = Field(..., gt=0)
    cost_per_brick: float = Field(..., gt=0)
    other_charges: float = Field(default=0.0, ge=0)
    amount_paid: float = Field(..., ge=0)


class StockAdjustmentRequest(BaseModel):
    kind: Literal["transfer", "return", "damage", "transfer_out"] = "transfer"
    batch_id: Optional[int] = Field(default=None, gt=0)
    change_amount: int  # positive = add stock, negative = remove stock (validated non-zero in the endpoint)
    note: str = Field(..., min_length=1)
