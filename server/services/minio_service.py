from minio import Minio
from minio.error import S3Error
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET

# Inicializar o cliente MinIO
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Defina como True se usar HTTPS
)

# Verificar se o bucket existe, se não, criar
if not client.bucket_exists(MINIO_BUCKET):
    client.make_bucket(MINIO_BUCKET)

def upload_file(file, file_location):
    try:
        client.put_object(
            MINIO_BUCKET, file_location, file.file, length=-1, part_size=10*1024*1024
        )
    except S3Error as err:
        raise err

def list_files():
    try:
        objects = client.list_objects(MINIO_BUCKET, prefix="/", recursive=True)
        return [obj.object_name for obj in objects]
    except S3Error as err:
        raise err

def download_file(filename):
    try:
        file_location = f"images/{filename}"
        return client.get_object(MINIO_BUCKET, file_location)
    except S3Error as err:
        raise err

def delete_file(filename):
    try:
        file_location = f"images/{filename}"
        client.remove_object(MINIO_BUCKET, file_location)
    except S3Error as err:
        raise err
