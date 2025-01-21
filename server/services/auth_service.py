import random
from datetime import datetime, timedelta
from services.email_service import send_email
from fastapi import HTTPException
from services.jwt_service import get_password_hash, verify_password
from services.jwt_service import create_access_token
from models.user_models import UserCreate, UserOut
from pymongo import MongoClient
from modules.db import users_collection

# Serviço de registro de usuários
async def register_user_service(user: UserCreate) -> UserOut:
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email já está registrado")
    hashed_password = get_password_hash(user.password)
    user_data = {
        "name": user.name,
        "email": user.email,
        "role": "user",
        "phone": user.phone,
        "hashed_password": hashed_password,
        "grad_year": user.grad_year,}
    users_collection.insert_one(user_data)
    return UserOut(name=user.name, email=user.email)

# Serviço de autenticação de usuário
async def authenticate_user_service(form_data):
    user = users_collection.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    access_token = create_access_token(data={"sub": str(user["_id"]), "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}


def generate_reset_code() -> str:
    return str(random.randint(1000, 9999))

# Função para processar o pedido de reset de senha
async def request_reset_password(email: str):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    # Gerar código de reset
    reset_code = generate_reset_code()
    # Armazenar o código no banco de dados com um tempo de expiração
    expiration_time = datetime.utcnow() + timedelta(minutes=10)  # O código expira em 10 minutos
    users_collection.update_one(
        {"email": email},
        {"$set": {"reset_code": reset_code, "reset_code_expiration": expiration_time}},
        upsert=True
    )
    # Enviar o código de reset por e-mail
    subject = "Código para resetar sua senha"
    body = f"Olá, para resetar sua senha, use o código: {reset_code}. Este código expirará em 10 minutos."
    send_email(subject, body, email)
    return {"message": "Código de reset enviado para seu e-mail"}
