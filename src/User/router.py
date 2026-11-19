
from fastapi import APIRouter, Request, status, Depends
from sqlalchemy.orm import Session
from User.Schema import UserLoginSchema, UserSchema, UserResponseSchema, UserLoginResponseSchema
from src.User import controller
from utils import db
from utils.db import get_db
from utils.db import get_db

user_router = APIRouter(prefix="/user")

@user_router.post("/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
def register_user(body: UserSchema, db: Session = Depends(get_db)):
    return controller.Register(body, db)

@user_router.get("/is_auth", response_model = UserResponseSchema, status_code=status.HTTP_200_OK)
def is_auth(request: Request, db: Session = Depends(get_db)):
    return controller.is_authenticated(request, db)

@user_router.post("/login", response_model=UserLoginResponseSchema, status_code = status.HTTP_200_OK)
def login(body: UserLoginSchema, db: Session = Depends(get_db)):
    return controller.login_user(body, db)

