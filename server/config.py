import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_FROM_PASSWORD = os.getenv("EMAIL_FROM_PASSWORD")
SECRET_KEY_JWT = os.getenv("SECRET_KEY_JWT")
