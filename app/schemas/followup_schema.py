from pydantic import BaseModel, conint


class UpdateDelaiRelanceSchema(BaseModel):
    delai_avant_relance: conint(ge=1, le=90)
