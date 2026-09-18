"""
main.py
-------
This is the entry point of the PashuPrint backend application.

Running this file (via uvicorn) starts the FastAPI server.
It is responsible for:
- Creating the database tables (if they don't exist yet)
- Setting up CORS so a React frontend can call this API
- Registering (including) all the route files from routers/
- Providing a simple health-check route at "/"
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import registration, verification, claims

# Create all database tables defined in models.py, if they don't already exist.
# (In a bigger project you'd use migrations, e.g. Alembic, instead of this.)
Base.metadata.create_all(bind=engine)

# Create the FastAPI app.
# The title/description show up automatically in the Swagger docs at /docs
app = FastAPI(
    title="PashuPrint API",
    description="Livestock biometric identity verification system (backend skeleton). "
    "ML model responses are currently mocked.",
    version="0.1.0",
)

# ---------- CORS setup ----------
# This allows a frontend (e.g. React app running on localhost:3000) to make
# requests to this backend. For development we allow all origins; tighten
# this later for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins (fine for local development)
    allow_credentials=True,
    allow_methods=["*"],       # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],       # Allow all headers
)

# ---------- Register routers ----------
# Each router file defines a related group of endpoints.
app.include_router(registration.router)
app.include_router(verification.router)
app.include_router(claims.router)


@app.get("/")
def root():
    """Simple health-check endpoint to confirm the server is running."""
    return {"message": "PashuPrint API is running. Visit /docs for Swagger UI."}
