from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from services.minio_service import delete_file, download_file, list_files, upload_file

router = APIRouter()

@router.delete("/delete/{filename}")
async def delete_image(filename: str):
    try:
        delete_file(filename)
        return {"message": f"File '{filename}' deleted successfully."}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error deleting file: {err}")

@router.get("/download/{filename}")
async def download_image(filename: str):
    try:
        file = download_file(filename)
        return StreamingResponse(file, media_type="image/jpeg")
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error downloading file: {err}")

@router.get("/images/")
async def list_images():
    try:
        files = list_files()
        return {"files": files}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error listing files: {err}")

@router.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    try:
        file_location = f"images/{file.filename}"
        upload_file(file, file_location)
        return {"message": f"File '{file.filename}' uploaded successfully.", "file_location": file_location}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error uploading file: {err}")
