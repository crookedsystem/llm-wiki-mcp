from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class MutableModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
