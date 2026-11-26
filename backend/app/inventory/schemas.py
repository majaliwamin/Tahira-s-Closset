from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


MovementType = Literal[
    "opening_stock",
    "restocking",
    "sale",
    "reservation",
    "reservation_release",
    "return",
    "damaged_stock",
    "lost_stock",
    "manual_correction",
    "stock_transfer",
]


class VariantBase(BaseModel):
    size: str = Field(default="Default", min_length=1, max_length=80)
    color: str = Field(default="Default", min_length=1, max_length=80)
    variant_sku: str = Field(min_length=1, max_length=120)
    stock_quantity: int = Field(default=0, ge=0)
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    barcode: Optional[str] = Field(default=None, max_length=120)
    low_stock_threshold: int = Field(default=3, ge=0, le=100000)
    is_active: bool = True

    @field_validator("size", "color", "variant_sku")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("Value cannot be empty")
        return v

    @field_validator("barcode")
    @classmethod
    def strip_barcode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None


class VariantCreate(VariantBase):
    product_id: int


class VariantUpdate(BaseModel):
    size: Optional[str] = Field(default=None, min_length=1, max_length=80)
    color: Optional[str] = Field(default=None, min_length=1, max_length=80)
    variant_sku: Optional[str] = Field(default=None, min_length=1, max_length=120)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    barcode: Optional[str] = Field(default=None, max_length=120)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0, le=100000)
    is_active: Optional[bool] = None
    reason: Optional[str] = Field(default=None, max_length=500)
    reference_number: Optional[str] = Field(default=None, max_length=120)


class RestockRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    quantity_received: int = Field(gt=0, le=1000000)
    supplier: str = Field(default="", max_length=200)
    cost_price: Optional[float] = Field(default=None, ge=0)
    reference_number: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)


class StockAdjustRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    new_quantity: int = Field(ge=0, le=1000000)
    reason: str = Field(min_length=2, max_length=500)
    reference_number: str = Field(default="", max_length=120)
    movement_type: Literal["manual_correction", "damaged_stock", "lost_stock", "return", "stock_transfer", "reservation", "reservation_release", "sale"] = "manual_correction"


class StockDeltaRequest(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    quantity: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=2, max_length=500)
    reference_number: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)


class BulkVariantUpdate(BaseModel):
    variant_ids: list[int] = Field(min_length=1)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    reason: str = Field(default="Bulk inventory update", min_length=2, max_length=500)


class BulkProductUpdate(BaseModel):
    product_ids: list[int] = Field(min_length=1)
    is_active: Optional[bool] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    supplier: Optional[str] = None
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)


class InventoryImportRow(BaseModel):
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    variant_sku: Optional[str] = None
    size: str = "Default"
    color: str = "Default"
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    cost_price: Optional[float] = Field(default=None, ge=0)
    selling_price: Optional[float] = Field(default=None, ge=0)
    barcode: Optional[str] = None
    is_active: Optional[bool] = None
    reason: str = "CSV import"
    reference_number: str = ""


class InventoryImportPreview(BaseModel):
    rows: list[InventoryImportRow]
    apply: bool = False
