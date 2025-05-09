# app/schemas/unite_produit_schema.py

from pydantic import BaseModel
from typing import List

class AddUnitesRequest(BaseModel):
    nombre: int
    prefixe: str = "TRAC-"
