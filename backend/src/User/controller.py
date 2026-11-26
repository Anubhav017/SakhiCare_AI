
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.User.Schema import UserSchema, UserLoginSchema, UserLoginResponseSchema
from fastapi import status, Request, HTTPException

from src.User.models import UserModel
from src.User.roles import managed_users
import jwt

from datetime import datetime, timedelta
from src.utils.config import settings
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def Register(body: UserSchema, db: Session):    
    data = body.model_dump()
    is_user = db.query(UserModel).filter(UserModel.username == data['username']).first()
    if is_user:
        raise HTTPException(status_code=400, detail="Username already exist")

    is_user = db.query(UserModel).filter(UserModel.email == data['email']).first()
    if is_user:
        raise HTTPException(status_code=400, detail="Email already exist")

    hashed_password = get_password_hash(data['password'])

    user = UserModel(name=data['name'], username=data['username'], email=data['email'], hashed_password = hashed_password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def authenticate_credentials(body: UserLoginSchema, db: Session) -> UserModel:
    user = db.query(UserModel).filter(UserModel.username == body.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username")

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    
    return user


def login_user(body: UserLoginSchema, db: Session):
    user = authenticate_credentials(body, db)
    token = jwt.encode({"_id": user.id, "exp": datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"token": token}

def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)

def is_authenticated(request: Request, db: Session):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    token = auth_header.split(" ")[-1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
        user_id = payload.get("_id")
        exp_time = payload.get("exp")

        current_time = datetime.now().timestamp()
        if current_time > exp_time:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
        
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        return user
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
def get_password_hash(password: str):
    return password_hash.hash(password)

def managed_ashas(db: Session, admin_id: int) -> list[UserModel]:
    return managed_users(db, admin_id)
