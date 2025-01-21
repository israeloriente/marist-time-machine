from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    grad_year: int

class UserOut(BaseModel):
    name: str
    email: EmailStr
