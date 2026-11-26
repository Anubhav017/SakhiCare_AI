
from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from sqlalchemy.orm import Session
from src.User.Schema import AdminOnboardingSchema, BrowserAccountSchema, ManagedAshaSchema, ManagedMemberSchema, MemberAccessUpdateSchema, OnboardedAdminSchema, BrowserLoginSchema, UserLoginSchema, UserSchema, UserResponseSchema, UserLoginResponseSchema
from src.User import browser_session, controller
from src.User.roles import is_supervisor, managed_accounts, update_member_access
from src.User.models import UserModel
from sqlalchemy import select
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
    if not is_supervisor(admin):
        raise HTTPException(403, "Supervisor access required")
    response.headers["Cache-Control"] = "no-store"
    return controller.managed_ashas(db, admin.id)


@user_router.get("/hierarchy", response_model=list[ManagedMemberSchema])
def read_user_hierarchy(request: Request, response: Response, db: Session = Depends(get_db)):
    user = browser_session.get_session(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Admin workspace access required")
    response.headers["Cache-Control"] = "private, no-store"
    return managed_accounts(db, user.id)


@user_router.patch("/hierarchy/{member_id}", response_model=ManagedMemberSchema,
                   dependencies=[Depends(browser_session.require_session_header)])
def change_member_access(member_id: int, body: MemberAccessUpdateSchema, request: Request,
                         response: Response, db: Session = Depends(get_db)):
    user = browser_session.get_session(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Only the Admin can manage workspace roles")
    member = update_member_access(db, user.id, member_id, body.role, body.reports_to_id)
    response.headers["Cache-Control"] = "private, no-store"
    return {"id": member.id, "name": member.name, "username": member.username,
            "email": member.email, "role": member.role, "reports_to_id": member.admin_id}


def _require_onboarding_admin(request: Request, db: Session) -> UserModel:
    user = browser_session.get_session(request, db)
    if user.role != "super_admin":
        raise HTTPException(403, "SakhiCare Super Admin access required")
    return user


@user_router.get("/onboarding/admins", response_model=list[OnboardedAdminSchema])
def list_organization_admins(request: Request, response: Response, db: Session = Depends(get_db)):
    _require_onboarding_admin(request, db)
    response.headers["Cache-Control"] = "private, no-store"
    return db.scalars(select(UserModel).where(
        UserModel.role == "admin",
    ).order_by(UserModel.name, UserModel.id)).all()


@user_router.post("/onboarding/admins", response_model=OnboardedAdminSchema, status_code=status.HTTP_201_CREATED,
                  dependencies=[Depends(browser_session.require_session_header)])
def create_organization_admin(body: AdminOnboardingSchema, request: Request, response: Response,
                              db: Session = Depends(get_db)):
    _require_onboarding_admin(request, db)
    username = body.username.strip()
    email = body.email.strip().lower()
    if db.scalar(select(UserModel.id).where(UserModel.username == username)):
        raise HTTPException(409, "That username is already in use")
    if db.scalar(select(UserModel.id).where(UserModel.email == email)):
        raise HTTPException(409, "That email is already in use")
    admin = UserModel(
        name=body.name.strip(), username=username, email=email,
        hashed_password=controller.get_password_hash(body.password),
        role="admin", admin_id=None,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    response.headers["Cache-Control"] = "private, no-store"
    return admin
