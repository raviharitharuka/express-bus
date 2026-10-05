from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """snake_case in Python, camelCase on the wire (see API_CONTRACT.md)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
