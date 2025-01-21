from minio import Minio
from minio.error import S3Error
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
import io

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
        # Lê o conteúdo do arquivo
        file_content = file.file.read()
        # Verifique se o conteúdo do arquivo foi lido corretamente
        if not file_content:
            raise ValueError("O arquivo está vazio ou não foi lido corretamente")
        # Faça o upload para o MinIO
        client.put_object(
            MINIO_BUCKET,
            file_location,  # O local onde o arquivo será armazenado
            io.BytesIO(file_content),  # Converte o conteúdo do arquivo para BytesIO
            len(file_content),  # Tamanho do arquivo
            part_size=10*1024*1024  # Tamanho de cada parte no upload
        )
        print(f"Arquivo {file_location} carregado com sucesso.")
        return file_location  # Retorna o local do arquivo no MinIO (ou pode retornar URL)
    except S3Error as err:
        # Captura erros específicos do MinIO
        raise Exception(f"Erro ao tentar fazer upload para o MinIO: {err}")
    except ValueError as err:
        # Captura erro de arquivo vazio
        raise Exception(f"Erro no arquivo: {err}")
    except Exception as err:
        # Captura qualquer outro erro
        raise Exception(f"Ocorreu um erro inesperado: {err}")

def list_files():
    try:
        objects = client.list_objects(MINIO_BUCKET, prefix="/2016", recursive=True)
        return [obj.object_name for obj in objects]
    except S3Error as err:
        raise err

def download_file(filename):
    try:
        file_location = f"{filename}"
        return client.get_object(MINIO_BUCKET, file_location)
    except S3Error as err:
        raise err

def delete_file(filename):
    try:
        file_location = f"{filename}"
        client.remove_object(MINIO_BUCKET, file_location)
    except S3Error as err:
        raise err
