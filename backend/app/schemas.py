from typing import Literal, Optional
from pydantic import BaseModel

class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    keep: Optional[Literal["old", "new"]] = None
    # only used when item_type == "conflict", picks which of the two
    # disagreeing values wins. Defaults to "new" if not specified.