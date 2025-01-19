from fastapi import FastAPI
from api.upload import router as upload_router
from api.list import router as list_router
from api.download import router as download_router
from api.delete import router as delete_router

app = FastAPI()

# Registrar os routers
app.include_router(upload_router)
app.include_router(list_router)
app.include_router(download_router)
app.include_router(delete_router)
