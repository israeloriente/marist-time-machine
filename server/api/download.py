from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from services.minio_service import download_file

router = APIRouter()

@router.get("/download/{filename}")
async def download_image(filename: str):
    try:
        file = download_file(filename)
        return StreamingResponse(file, media_type="image/jpeg")
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error downloading file: {err}")
