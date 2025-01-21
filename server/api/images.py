from fastapi import APIRouter, HTTPException, File, UploadFile, APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.minio_service import list_files, upload_file
from services.jwt_service import get_current_user
from services.mongo_service import save_image_to_db
from services.milvus_service import process_images, find_similar_faces
import base64

router = APIRouter()

class ImageRequest(BaseModel):
    image: str  # O campo 'image' será do tipo string

@router.post("/add-embedding/")
async def list_images():
    try:
        files = process_images()
        return {"files": files}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error listing files: {err}")

@router.post("/compare-embedding/")
async def list_images(image_request: ImageRequest):
    try:
        # Decodifica a imagem base64
        image_data = base64.b64decode(image_request.image)

        # Passa a imagem para o método de comparação
        similar_faces = find_similar_faces(image_data)
        return {"similar_faces": similar_faces}  # Retorna os resultados das faces similares
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error listing files: {err}")

@router.post("/upload/")
async def upload_image(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="User not authenticated")
        file_location = f"/{current_user['grad_year']}/{current_user['email']}/{file.filename}"
        file_url = upload_file(file, file_location)
        image_id = await save_image_to_db(current_user["_id"], file_url)
        return {"message": f"File '{file.filename}' uploaded successfully.", "file_url": file_url, "image_id": image_id}
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Error uploading file: {err}")
