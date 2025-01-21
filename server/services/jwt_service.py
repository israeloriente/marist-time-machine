from jose import jwt, JWTError
from datetime import datetime, timedelta
from passlib.context import CryptContext
from config import SECRET_KEY_JWT
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from modules.db import users_collection
from bson import ObjectId

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 90
# Configurações de segurança e JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        return None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Dependência para obter o usuário autenticado
def get_current_token(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    # Aqui você pode buscar o usuário no banco de dados, caso necessário
    return payload  # Retorna o payload do JWT, normalmente contém informações como o e-mail ou ID do usuário


def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    user_id = payload.get("sub")  # 'sub' contém o identificador único do usuário
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de autenticação inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
