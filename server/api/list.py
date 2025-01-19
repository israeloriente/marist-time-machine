from fastapi import APIRouter, HTTPException
from services.minio_service import list_files

router = APIRouter()

@router.get("/images/")
async def list_images():
    try:
        files = list_files()
        return {"files": files}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error listing files: {err}")
