from pydantic import BaseModel

class LoanFileCreate(BaseModel):
    """Defines what the REQUEST BODY must look like when someone calls
    POST /loan-files. FastAPI reads this, validates the incoming JSON
    against it automatically, and rejects bad requests (e.g. missing
    borrower_name) with a clear 422 error before your code even runs."""
    borrower_name: str