from fastapi import APIRouter, HTTPException, Depends, Request, status, Query
from database import engine, Base
from sqlalchemy import select, update, delete
from typing import List, Optional
import models, schemas
from database import engine, Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession

from services.venti_service import VentiConfigService

# 创建数据库表

# Base.metadata.create_all(bind=engine)

# app = FastAPI(title="Python CRUD System", description="基于FastAPI和SQLAlchemy的增删改查示例")

# router = APIRouter(prefix="/gran", tags=["仓房管理模块"])
router = APIRouter(tags=["仓房管理模块"])


# @router.post("/items/", response_model=ItemResponse, status_code=201)
# def create_new_item(item: ItemCreate, db: Session = Depends(get_db)):
#     """创建新项目"""
#     return create_item(db=db, item=item)

# @router.get("/items/", response_model=list[ItemResponse])
# def read_all_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     """获取所有项目，支持分页"""
#     items = get_items(db, skip=skip, limit=limit)
#     print("*** get items")
#     return items

# @router.get("/items/{item_id}", response_model=ItemResponse)
# def read_single_item(item_id: int, db: Session = Depends(get_db)):
#     """获取单个项目"""
#     print('to delete item')
#     db_item = get_item(db, item_id=item_id)
#     if db_item is None:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return db_item

# @router.put("/items/{item_id}", response_model=ItemResponse)
# def update_existing_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
#     """更新项目"""
#     db_item = update_item(db, item_id=item_id, item=item)
#     if db_item is None:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return db_item

# @router.delete("/items/{item_id}")
# def delete_existing_item(item_id: int, db: Session = Depends(get_db)):
#     """删除项目"""
#     success = delete_item(db, item_id=item_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return {"message": "Item deleted successfully"}



# 🎯 接口 1：【查】- 获取并筛选廒间列表（支持前端多条件过滤）

@router.get("/api/ventilation-modes", response_model=schemas.VentilationModePageResult)
async def get_venti_list(
    # house_code: Optional[int] = Query(None),
    # severity: Optional[str] = Query(None),
    # start_time: Optional[datetime] = Query(None),
    # end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    # 🎯 注入我们的 Service 层
    service: VentiConfigService = Depends(VentiConfigService)
):
    try:
        # 🚀 路由层变得极其干净，只负责调用 Service 并传递参数
        items, total = await service.get_ventilation_modes(
           
            page=page,
            size=size
            # page=page, size=size
        )
        # print('alarms, ', alarms)
        return {
            "total": total,
            "items": items
        }
    except Exception as e:
        print(f"Service 层执行异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统内部业务处理异常"
        )


# 🎯 接口 2：【增】- 新增廒间
@router.post("/api/ventilation-mode", response_model=schemas.VentilationModeOut, status_code=status.HTTP_201_CREATED)
async def create_granary(obj_in: schemas.VentilationModeCreate, db: AsyncSession = Depends(get_db)):
    # 校验编号唯一性
    # check_stmt = select(models.VentilationMode).where(models.VentilationMode.code == obj_in.code)
    # existing = (await db.execute(check_stmt)).scalar_one_or_none()
    # if existing:
    #     raise HTTPException(status_code=400, detail="该廒间编号已存在，请勿重复添加")
    print('in create venti-mode')
    new_venti_mode = models.VentilationMode(**obj_in.model_dump())
    db.add(new_venti_mode)
    await db.commit()
    await db.refresh(new_venti_mode)
    return new_venti_mode


# 🎯 接口 3：【改】- 依据 ID 修改廒间信息
@router.patch("/api/ventilation-mode/{item_id}", response_model=schemas.VentilationModeOut)
async def update_granary(request: Request, item_id: int, obj_in: schemas.VentilationModeUpdate, db: AsyncSession = Depends(get_db)):
    # 查询是否存在
    print('####查询模式信息')
    stmt = select(models.VentilationMode).where(models.VentilationMode.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    # 执行更新
    await db.execute(
        update(models.VentilationMode)
        .where(models.VentilationMode.id == item_id)
        .values(**obj_in.model_dump(exclude={"code"})) # 工业常识：禁止通过此接口修改主键 code
    )
    await db.commit()
    await db.refresh(db_item)

    # 同时更新内存中temp threshold
    # request.app.state.TEMP_UPPER_LIMIT = obj_in.max_temp
    print(f'【已更新模式{obj_in.start_humidity_diff}温度上限值】为{obj_in.end_humidity_diff}')
    return db_item


# 🎯 接口 4：【删】- 依据 ID 删除廒间
@router.delete("/api/ventilation-mode/{item_id}")
async def delete_granary(item_id: int, db: AsyncSession = Depends(get_db)):
    print('删除仓房信息')
    stmt = select(models.VentilationMode).where(models.VentilationMode.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    await db.execute(delete(models.VentilationMode).where(models.VentilationMode.id == item_id))
    await db.commit()
    return {"status": "success", "msg": f"成功删除 ID 为 {item_id} 的廒间"}
