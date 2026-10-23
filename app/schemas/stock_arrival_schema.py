from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StockArrivalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    reference: Optional[str] = Field(default=None, max_length=100)
    supplier_id: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = Field(default=None, max_length=2000)


class StockArrivalUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Le nom doit contenir au moins 2 caractères")
        return normalized


class StockArrivalLineCreate(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=10000)
    barcodes: list[str] = Field(default_factory=list, max_length=10000)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("barcodes")
    @classmethod
    def normalize_barcodes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value and value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Les codes-barres doivent être uniques")
        return normalized


class StockTransferItem(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=10000)
    unit_ids: list[int] = Field(default_factory=list)


class StockTransferCreate(BaseModel):
    destination_enterprise_id: int = Field(ge=1)
    items: list[StockTransferItem] = Field(min_length=1)
    notes: Optional[str] = Field(default=None, max_length=2000)
    source_arrival_id: Optional[int] = Field(default=None, ge=1)


class ArrivalTransferCreate(BaseModel):
    destination_enterprise_id: int = Field(ge=1)
    items: list[StockTransferItem] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)
