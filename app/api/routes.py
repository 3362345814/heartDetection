from fastapi import APIRouter

from app.api.endpoints import auth, cases, ultrasound_images, detection_results, detection_images, model_detection

# 创建主路由器
api_router = APIRouter()

# 包含各个功能模块的路由
api_router.include_router(auth.router, prefix="/auth", tags=["用户认证"])
api_router.include_router(cases.router, prefix="/cases", tags=["检查案例"])
api_router.include_router(ultrasound_images.router, prefix="/ultrasound-images", tags=["超声图像"])
api_router.include_router(detection_results.router, prefix="/detection-results", tags=["检测结果"])
api_router.include_router(detection_images.router, prefix="/detection-images", tags=["检测图像"])
api_router.include_router(model_detection.router, prefix="/cases", tags=["模型调用"])
