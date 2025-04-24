import os
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db.session import Base, engine

def init_db() -> None:
    """
    初始化数据库。
    """
    # 如果数据库不存在则创建
    create_db_if_not_exists()
    
    # 创建表
    Base.metadata.create_all(bind=engine)
    
    # 如果上传目录不存在则创建
    os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)

def create_db_if_not_exists() -> None:
    """
    如果数据库不存在则创建。
    """
    # 连接到MySQL服务器而不指定数据库
    db_uri = f"mysql+pymysql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}"
    engine_temp = create_engine(db_uri)
    
    # 如果数据库不存在则创建
    with engine_temp.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {settings.DATABASE_NAME}"))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("数据库初始化成功。")