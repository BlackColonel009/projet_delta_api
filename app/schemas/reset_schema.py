from pydantic import BaseModel

class ResetCodeSchema(BaseModel):
    code: str
