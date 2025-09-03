from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

# 创建路由器
router = APIRouter()

# 模板配置
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def root_page(request: Request):
    # 准备模板数据
    template_data = {
        "request": request,
        "status": {
            "ws_ready": True,  # 假设WebSocket已连接
            "active_subscriptions": 0,
            "subscription_stats": {
                "total": 0
            }
        },
        "subscriptions": [],
        "accounts": [],
        "configs": []
    }
    
    return templates.TemplateResponse("index.html", template_data)


# Serve individual pages
@router.get("/home")
async def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/accounts")
async def accounts_page(request: Request):
    return templates.TemplateResponse("accounts.html", {"request": request})


@router.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})
