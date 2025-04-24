from pydantic import BaseModel, Field

class Token(BaseModel):
    """用户登录成功后返回的令牌信息"""
    access_token: str = Field(..., description="访问令牌，用于后续请求认证")
    token_type: str = Field(..., description="令牌类型，通常为bearer")

class TokenPayload(BaseModel):
    """令牌的有效载荷内容"""
    sub: str = Field(None, description="令牌主题（通常是用户ID）")
    exp: int = Field(None, description="令牌过期时间（UNIX时间戳）")
