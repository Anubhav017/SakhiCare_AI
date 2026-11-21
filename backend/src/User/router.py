
from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from sqlalchemy.orm import Session
from src.User.Schema import BrowserAccountSchema, ManagedAshaSchema, BrowserLoginSchema, UserLoginSchema, UserSchema, UserResponseSchema, UserLoginResponseSchema
from src.User import browser_session, controller
from src.utils.db import get_db

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



@user_router.post(
    "/session", response_model=BrowserAccountSchema,
    dependencies=[Depends(browser_session.require_session_header)],
)
def create_session(body: BrowserLoginSchema, response: Response, db: Session = Depends(get_db)):
    user = controller.authenticate_credentials(body, db)
    if body.role is not None and user.role != body.role:
        raise HTTPException(status_code=400, detail="Choose the role that matches your account.")
    browser_session.set_session(response, user, body.remember)
    response.headers["Cache-Control"] = "no-store"
    return user


@user_router.get("/session", response_model=BrowserAccountSchema)
def read_session(request: Request, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return browser_session.get_session(request, db)


@user_router.delete(
    "/session", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(browser_session.require_session_header)],
)
def delete_session():
    response = Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
    browser_session.clear_session(response)
    return response


@user_router.get("/managed-ashas", response_model=list[ManagedAshaSchema])
def list_managed_ashas(request: Request, response: Response, db: Session = Depends(get_db)):
    admin = browser_session.get_session(request, db)
    if admin.role != "super_admin":
        raise HTTPException(403, "Super Admin access required")
    response.headers["Cache-Control"] = "no-store"
    return controller.managed_ashas(db, admin.id)
