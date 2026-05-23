from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

# ------------------------------
# 创建 FastAPI 应用实例
# ------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# ------------------------------
# 跨域中间件（如前后端分离时可配置）
# ------------------------------
# 开发阶段允许所有来源，生产环境应限制
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# 全局异常处理
# ------------------------------
class AppException(Exception):
    """业务异常基类，可在 core/permissions.py 中继承使用"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """捕获自定义业务异常，返回统一格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """覆盖默认 HTTPException 处理，统一响应结构（可选）"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """捕获未预料的异常，返回 500 且隐藏内部错误细节"""
    # 开发模式下可输出堆栈，生产环境仅返回通用消息
    if settings.DEBUG:
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ------------------------------
# 挂载各模块路由（预留，后续逐步接入）
# ------------------------------
from app.api import auth, users
app.include_router(auth.router)       # auth 路由已在内部定义了 prefix="/auth"
app.include_router(users.router)      # users 路由已在内部定义了 prefix="/users"

from app.api import auth, users, authors, books 
app.include_router(authors.router)   
app.include_router(books.router)

from app.api import admin
app.include_router(admin.router)

# 临时健康检查端点（确保服务可访问）
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}