from pymilvus import connections, list_collections, Collection, FieldSchema, CollectionSchema, DataType

# Configurações do Milvus
MILVUS_HOST = "127.0.0.1"
MILVUS_PORT = "19530"

# Conectar ao Milvus
connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
print("Conectado ao Milvus!")

# Criar índice para a coleção
def create_index(collection_name):
    collection = Collection(name=collection_name)
    index_params = {
        "index_type": "IVF_FLAT",  # Tipo de índice
        "metric_type": "L2",       # Métrica de distância
        "params": {"nlist": 128}   # Número de listas
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    print(f"Índice criado para a coleção '{collection_name}'.")

# Listar todas as coleções
def list_all_collections():
    collections = list_collections()
    print("Coleções no Milvus:")
    for collection_name in collections:
        print(f"- {collection_name}")
    return collections

# Obter todos os dados de uma coleção
def get_all_data_from_collection(collection_name):
    collection = Collection(name=collection_name)

    # Certifique-se de que o índice foi criado
    if not collection.has_index():
        create_index(collection_name)

    # Carregar a coleção na memória
    collection.load()

    # Fazer uma consulta para pegar todos os dados
    results = collection.query(expr="id >= 0", output_fields=["*"])  # Filtro para buscar todos os dados
    print(f"Dados da coleção '{collection_name}':")
    for result in results:
        print(result)

# Listar coleções e obter dados
collections = list_all_collections()
for collection_name in collections:
    get_all_data_from_collection(collection_name)

