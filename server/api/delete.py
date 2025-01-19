from fastapi import APIRouter, HTTPException
from services.minio_service import delete_file

router = APIRouter()

@router.delete("/delete/{filename}")
async def delete_image(filename: str):
    try:
        delete_file(filename)
        return {"message": f"File '{filename}' deleted successfully."}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error deleting file: {err}")
