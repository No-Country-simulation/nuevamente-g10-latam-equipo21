from pydantic import BaseModel, ConfigDict


class ContractSchema(BaseModel):
    """Base estricta para los modelos que forman parte del contrato público."""

    model_config = ConfigDict(extra="forbid", strict=True)
