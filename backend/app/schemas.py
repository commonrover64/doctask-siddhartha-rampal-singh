from typing import Literal, Optional
from pydantic import BaseModel

class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    keep: Optional[Literal["old", "new"]] = None
    # only used when item_type == "conflict", picks which of the two
    # disagreeing values wins. Defaults to "new" if not specified.

class LoanFileCreate(BaseModel):
    """Defines what the REQUEST BODY must look like when someone calls
    POST /loan-files. FastAPI reads this, validates the incoming JSON
    against it automatically, and rejects bad requests (e.g. missing
    borrower_name) with a clear 422 error before your code even runs."""
    borrower_name: str