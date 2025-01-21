from pymongo import MongoClient

# Configurações do MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["MPX"]
users_collection = db["users"]
photos_collection = db["photos"]
