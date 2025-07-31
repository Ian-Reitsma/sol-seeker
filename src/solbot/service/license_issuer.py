from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os

from prometheus_fastapi_instrumentator import Instrumentator

from solbot.utils.license import LicenseManager
from . import publisher

app = FastAPI()

RPC_HTTP = os.getenv("RPC_HTTP", "https://api.mainnet-beta.solana.com")
if os.getenv("LICENSE_API_TOKEN"):
    raise RuntimeError("Static LICENSE_API_TOKEN not allowed; use JWTs")

lm = LicenseManager(rpc_http=RPC_HTTP)
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app)

def verify_jwt(token: str) -> bool:
    """Validate bearer JWT. TODO: implement real verification by 2025-08-15."""
    return bool(token)

class IssueRequest(BaseModel):
    wallet: str
    demo: bool = False

@app.post("/issue")
def issue(req: IssueRequest, authorization: str = Header(None)):
    if not verify_jwt(authorization.replace("Bearer ", "") if authorization else ""):
        raise HTTPException(status_code=401, detail="Unauthorized")
    publisher.publish_issue(req.dict())
    return {"queued": True}


@app.get("/healthz")
def healthz():
    lm._client().is_connected()
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ok"}
