import random
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from services.auth_service import register_user_service, authenticate_user_service
from models.user_models import UserCreate, UserOut
from services.jwt_service import get_password_hash
from services.email_service import send_email
from modules.db import users_collection

router = APIRouter(prefix="/auth", tags=["auth"])

class ResetPasswordRequest(BaseModel):
    email: str

class ResetPassword(BaseModel):
    new_password: str
    code: str

@router.post("/reset_password_request")
async def reset_password_request(request: ResetPasswordRequest):
    email = request.email
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    # Gerar código aleatório de 4 dígitos
    reset_code = str(random.randint(1000, 9999))
    users_collection.update_one({"email": email}, {"$set": {"reset_code": reset_code}})
    subject = "Código de reset de senha"
    body = f"Seu código de reset é: {reset_code}"
    send_email(subject, body, email)
    return {"message": "Código de reset enviado para seu e-mail"}

@router.post("/reset_password")
async def reset_password(request: ResetPassword):
    new_password = request.new_password
    code = request.code
    user = users_collection.find_one({"reset_code": code})
    if not user:
        raise HTTPException(status_code=400, detail="Código de reset inválido")
    hashed_password = get_password_hash(new_password)
    users_collection.update_one({"reset_code": code}, {"$set": {"hashed_password": hashed_password, "reset_code": None}})
    return {"message": "Senha atualizada com sucesso"}

# Endpoint de registro
@router.post("/register", response_model=UserOut)
async def register_user(user: UserCreate):
    return await register_user_service(user)

# Endpoint de login
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    return await authenticate_user_service(form_data)
