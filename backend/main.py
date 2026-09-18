"""
main.py
-------
Entry point of the PashuPrint backend application.

Running this file (via uvicorn) starts the FastAPI server. It is
responsible for:
- Creating the SQLite tables (if they don't exist yet) via db.init_db()
- Setting up CORS so a future React/Streamlit frontend can call this API
- Registering all the route files from routers/
- Providing a simple health-check route at "/"
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from routers import registration, verification, claims, fraud

# Create the SQLite tables defined in db.py, if they don't already exist.
# db.py is the ONLY place table schemas are defined -- there is no ORM
# layer duplicating this.
db.init_db()

app = FastAPI(
    title="PashuPrint API",
    description=(
        "Livestock biometric identity verification system (backend skeleton). "
        "ML model responses are currently MOCKED -- see services/mock_ml.py."
    ),
    version="0.1.0",
)

# ---------- CORS setup ----------
# Allows a frontend (e.g. React on localhost:3000) to call this API.
# Wide open here for local development only; tighten before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Register routers ----------
app.include_router(registration.router)
app.include_router(verification.router)
app.include_router(claims.router)
app.include_router(fraud.router)


@app.get("/")
def root():
    """Simple health-check endpoint to confirm the server is running."""
    return {"message": "PashuPrint API is running. Visit /docs for Swagger UI."}
