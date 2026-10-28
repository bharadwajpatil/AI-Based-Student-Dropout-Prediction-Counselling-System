from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict


def validate_object_id(v: Any) -> str:
    """Validates that a value is an ObjectId or valid 24-char hex string, returning string."""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError(f"Invalid ObjectId: {v}")


PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]


def convert_object_ids_for_mongo(obj: Any) -> Any:
    """Recursively converts PyObjectId string fields to bson.ObjectId for MongoDB persistence."""
    if isinstance(obj, dict):
        new_dict: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "_id" and isinstance(v, str) and ObjectId.is_valid(v):
                new_dict[k] = ObjectId(v)
            elif (k.endswith("_id") or k.endswith("_ids")) and v is not None:
                if isinstance(v, str) and ObjectId.is_valid(v):
                    new_dict[k] = ObjectId(v)
                elif isinstance(v, list):
                    new_dict[k] = [
                        (
                            ObjectId(item)
                            if isinstance(item, str) and ObjectId.is_valid(item)
                            else item
                        )
                        for item in v
                    ]
                else:
                    new_dict[k] = convert_object_ids_for_mongo(v)
            else:
                new_dict[k] = convert_object_ids_for_mongo(v)
        return new_dict
    elif isinstance(obj, list):
        return [convert_object_ids_for_mongo(item) for item in obj]
    return obj


class MongoBaseModel(BaseModel):
    """Base model enforcing Ground Rule 5: reject unknown fields (extra='forbid')."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    def to_mongo(self, exclude_none: bool = False) -> dict[str, Any]:
        """Serializes model to a MongoDB-ready dictionary with native BSON types."""
        data = self.model_dump(by_alias=True, exclude_none=exclude_none)
        return convert_object_ids_for_mongo(data)
