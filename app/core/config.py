from typing import List, Union
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

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
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # JWT设置
    SECRET_KEY: str = "your-secret-key-here"  # 在生产环境中，使用安全的随机密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 文件存储设置
    UPLOAD_DIRECTORY: str = "uploads"
    
    class Config:
        case_sensitive = True

settings = Settings()