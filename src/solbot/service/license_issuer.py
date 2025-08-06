from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os
import jwt

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
    """Validate bearer JWT.

    Decodes ``token`` using a trusted secret or public key and verifies the
    signature along with ``exp`` (expiration), ``iss`` (issuer) and ``aud``
    (audience) claims.  Returns ``True`` only when all checks pass.
    """

    secret = os.getenv("LICENSE_JWT_SECRET")
    public_key = os.getenv("LICENSE_JWT_PUBLIC_KEY")
    issuer = os.getenv("LICENSE_JWT_ISSUER", "solbot-license-service")
    audience = os.getenv("LICENSE_JWT_AUDIENCE", "solbot-clients")

    key = public_key or secret
    if not key or not token:
        return False

    algorithm = "RS256" if public_key else "HS256"

    try:
        jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
        return True
    except jwt.PyJWTError:
        return False

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
