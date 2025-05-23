import os
from typing import List, Union

from dotenv import load_dotenv
from pydantic import validator
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Heart Disease Detection API"

    # 数据库设置
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: str = "3306"
    DATABASE_USER: str = "root"
    DATABASE_PASSWORD: str = "12345678"
    DATABASE_NAME: str = "heart_detection"

    SQLALCHEMY_DATABASE_URI: str = f"mysql+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

    # CORS设置
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # JWT设置
    SECRET_KEY: str = "lxh666"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    class Config:
        case_sensitive = True
        env_file = "../../.env"

    COS_SECRET_ID: str = os.getenv('COS_SECRET_ID')
    COS_SECRET_KEY: str = os.getenv('COS_SECRET_KEY')
    COS_BUCKET_NAME: str = os.getenv('COS_BUCKET_NAME')
    COS_REGION: str = os.getenv('COS_REGION')

    OCR_APP_ID: str = os.getenv('OCR_APP_ID')
    OCR_API_KEY: str = os.getenv('OCR_API_KEY')
    OCR_API_SECRET: str = os.getenv('OCR_API_SECRET')


settings = Settings()
