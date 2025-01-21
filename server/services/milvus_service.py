import requests
from deepface import DeepFace
from io import BytesIO
from PIL import Image  # Biblioteca para trabalhar com imagens
import numpy as np  # Para conversão para array
from pymilvus import connections, Collection, DataType, CollectionSchema, FieldSchema, utility, Index, IndexType
from modules.db import photos_collection
import time  # Importando time para aguardar a construção do índice

# Conectar ao Milvus
connections.connect("default", host="localhost", port="19530")

# Configurar a coleção no Milvus
collection_name = "embeddings"

# # Deletar a coleção anterior, se ela existir
# if collection_name in utility.list_collections():
#     collection = Collection(collection_name)
#     collection.drop()  # Remove a coleção existente

# Criar nova coleção com schema correto
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=4096),  # Dimensão do modelo VGG-Face
    FieldSchema(name="image_url", dtype=DataType.VARCHAR, max_length=255),
]
schema = CollectionSchema(fields, "Collection de embeddings de imagens")

# Verificar se a coleção existe e carregar
if utility.has_collection(collection_name):
    collection = Collection(collection_name)
else:
    collection = Collection(name=collection_name, schema=schema)

# Função para processar imagens do MongoDB
def process_images():
    # Buscar imagens com status "pending"
    photos = photos_collection.find({"status": "pending"})

    for photo in photos:
        try:
            image_url = f"http://localhost:9000/mybucket{photo.get('image_url')}"
            if not image_url:
                print(f"Documento {photo['_id']} não possui uma URL de imagem.")
                continue

            # Baixar a imagem diretamente para a memória
            response = requests.get(image_url)
            response.raise_for_status()

            # Converter o conteúdo baixado em uma imagem e depois em array NumPy
            image = Image.open(BytesIO(response.content)).convert("RGB")  # Certificar-se de que está no formato RGB
            image_array = np.array(image)  # Converte a imagem para um array NumPy

            # Gerar os vector embeddings usando DeepFace
            try:
                embeddings = DeepFace.represent(
                    img_path=image_array,  # Agora passamos o array NumPy
                    model_name="VGG-Face",
                    detector_backend="opencv",
                    enforce_detection=True  # Forçar detecção de rostos
                )

                # Iterar sobre os embeddings (múltiplos rostos na imagem)
                for idx, result in enumerate(embeddings):
                    embedding = result["embedding"]
                    collection.insert([{"embedding": embedding, "image_url": image_url}])  # Inserir no Milvus

                # Atualizar o status da foto no MongoDB
                photos_collection.update_one(
                    {"_id": photo["_id"]},
                    {"$set": {"status": "processed", "embedding_count": len(embeddings)}}
                )

            except ValueError as ve:
                # Tratar o caso onde não há rosto detectado
                print(f"Erro de detecção de rosto na imagem {photo['_id']}: {ve}")
                # Se necessário, você pode marcar como 'sem rosto detectado' ou algo similar
                photos_collection.update_one(
                    {"_id": photo["_id"]},
                    {"$set": {"status": "no_face_detected"}}
                )

            except Exception as e:
                # Captura outras exceções gerais
                print(f"Erro inesperado ao processar a imagem {photo['_id']}: {e}")

        except Exception as e:
            print(f"Erro ao processar a imagem {photo['_id']}: {e}")


def find_similar_faces(image_data: bytes, threshold: float = 0.80):
    try:
        # Converte os dados binários para uma imagem PIL
        image = Image.open(BytesIO(image_data)).convert("RGB")  # Certificar-se de que está no formato RGB
        image_array = np.array(image)  # Converte a imagem para um array NumPy

        # Gerar os vector embeddings usando DeepFace
        embeddings = DeepFace.represent(
            img_path=image_array,  # Agora passamos o array NumPy
            model_name="VGG-Face",
            detector_backend="opencv",
            enforce_detection=True  # Forçar detecção de rostos
        )

        if not embeddings:
            print("Nenhum rosto detectado na imagem fornecida.")
            return []

        # Obter o embedding do rosto detectado (no caso, o primeiro rosto)
        query_embedding = embeddings[0]["embedding"]

        print(query_embedding)

        # Buscar todos os embeddings na coleção do Milvus
        # Realizar a busca para encontrar os embeddings mais similares
        search_result = collection.search(
            data=[query_embedding],  # O vetor de embedding para comparar
            anns_field="embedding",  # O campo de embedding na coleção
            param={"nprobe": 10},  # Parâmetro para busca (definir quantidade de vizinhos próximos)
            limit=5,  # Limitar a 5 resultados mais próximos
        )

        # Filtrar resultados com base no limiar de similaridade
        similar_faces = []
        for result in search_result[0]:
            if result.distance <= threshold:
                # Aqui buscamos a URL associada ao embedding
                image_url = result.entity.get("image_url", "URL não disponível")
                similar_faces.append({
                    "image_url": image_url,
                    "similarity_score": result.distance
                })

        return similar_faces

    except Exception as e:
        print(f"Erro ao processar a imagem: {e}")
        return []
