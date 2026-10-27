"""Types et base communs aux schémas Pydantic de tous les modules."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Sex = Literal["M", "F", "U"]
Visibility = Literal["family", "branch", "board", "private"]
Certainty = Literal["documented", "oral", "uncertain"]
ParentKind = Literal["biological", "adoptive", "recognized"]
UnionKind = Literal["customary", "civil", "religious"]
EndReason = Literal["divorce", "death", "other"]
RoleName = Literal["member", "branch_head", "treasurer", "secretary", "admin"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
