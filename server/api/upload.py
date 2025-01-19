from fastapi import APIRouter, HTTPException, File, UploadFile
from services.minio_service import upload_file

router = APIRouter()

@router.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        file_location = f"images/{file.filename}"
        upload_file(file, file_location)
        return {"message": f"File '{file.filename}' uploaded successfully.", "file_location": file_location}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error uploading file: {err}")
