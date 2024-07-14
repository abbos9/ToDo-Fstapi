from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timedelta
from typing import Annotated, Union
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext

from config import ALGORITHM, SECRET_KEY
from database import SessionLocal
from models import Users
from schemas import CreateUserSchema, TokenSchema, UserResponseSchema


# security
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")

router = APIRouter(
    prefix="/auth",
    tags=['auth']
)


# dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


# crud/mechanic
def create_access_token(username: str, user_id: int, first_name: str, last_name: str, expires_delta: timedelta):
    encode = {
        "sub": username,
        "id": user_id,
        "first_name": first_name,
        "last_name": last_name
    }
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(db: Session, username: str, password: str):
    db_user = db.query(Users).filter(Users.username == username).first()
    if not db_user or not bcrypt_context.verify(password, db_user.hashed_password):
        return False
    return db_user

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate user."
            )
        db_user = db.query(Users).filter(Users.id == user_id).first()
        if db_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate user."
            )
        return {
            "id": db_user.id,
            "username": db_user.username,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "role": db_user.role
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate user"
        )

# end

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency,create_user_schema: CreateUserSchema):
    if db.query(Users).filter(Users.username == create_user_schema.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    create_user_model = Users(
        username=create_user_schema.username,
        hashed_password=bcrypt_context.hash(create_user_schema.password),
        first_name=create_user_schema.first_name,
        last_name=create_user_schema.last_name,
        role=create_user_schema.role,
        phone_num=create_user_schema.phone_num
    )
    db.add(create_user_model)
    db.commit()
    return create_user_model


@router.post('/token/', response_model=TokenSchema)
async def login_by_access_token(db: db_dependency, data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user.")
    token = create_access_token(user.username, user.id, user.first_name, user.last_name, timedelta(minutes=10))

    return {
        'access_token': token,
        'token_type': 'bearer'
    }
