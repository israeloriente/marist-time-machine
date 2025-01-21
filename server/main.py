from fastapi import FastAPI
from api.auth import router as auth_router
from api.images import router as images_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Registrar os routers
app.include_router(auth_router)
app.include_router(images_router)
