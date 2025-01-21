from modules.db import photos_collection
from datetime import datetime

async def save_image_to_db(user_id: str, file_url: str):
    image_data = {
        "user_id": user_id,
        "image_url": file_url,
        "status": "pending",
        "uploaded_at": datetime.utcnow(),
    }

    # Insere o documento no banco de dados e espera a operação assíncrona ser concluída
    result = photos_collection.insert_one(image_data)

    # Retorna o ID do documento inserido como string
    return str(result.inserted_id)
