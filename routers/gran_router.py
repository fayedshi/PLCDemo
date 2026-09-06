from fastapi import APIRouter, HTTPException, Depends, status, Query
from database import engine, Base
from sqlalchemy import select, update, delete
from typing import List, Optional
import models, schemas
from database import engine, Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession

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
@router.get("/api/granary", response_model=List[schemas.GranaryOut])
async def read_granaries(
    name: Optional[str] = Query(None, description="模糊搜索名称或编号"),
    grain_type: Optional[str] = Query(None, description="精确品种筛选"),
    keeper: Optional[str] = Query(None, description="模糊搜索保管员"),
    db: AsyncSession = Depends(get_db)
    ):
    print("##########in search granary")
    stmt = select(models.Granary)
    
    # 🔍 动态拼接前端传来的查询条件
    if name:
        stmt = stmt.where(
            models.Granary.name.like(f"%{name}%") | 
            models.Granary.code.like(f"%{name}%")
        )
    if grain_type:
        stmt = stmt.where(models.Granary.grain_type == grain_type)
    if keeper:
        stmt = stmt.where(models.Granary.keeper.like(f"%{keeper}%"))
        
    result = await db.execute(stmt)
    return result.scalars().all()


# 🎯 接口 2：【增】- 新增廒间
@router.post("/api/granary", response_model=schemas.GranaryOut, status_code=status.HTTP_201_CREATED)
async def create_granary(obj_in: schemas.GranaryCreate, db: AsyncSession = Depends(get_db)):
    # 校验编号唯一性
    check_stmt = select(models.Granary).where(models.Granary.code == obj_in.code)
    existing = (await db.execute(check_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="该廒间编号已存在，请勿重复添加")
        
    new_granary = models.Granary(**obj_in.model_dump())
    db.add(new_granary)
    await db.commit()
    await db.refresh(new_granary)
    return new_granary


# 🎯 接口 3：【改】- 依据 ID 修改廒间信息
@router.put("/api/granary/{item_id}", response_model=schemas.GranaryOut)
async def update_granary(item_id: int, obj_in: schemas.GranaryUpdate, db: AsyncSession = Depends(get_db)):
    # 查询是否存在
    print('查询仓房信息')
    stmt = select(models.Granary).where(models.Granary.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    # 执行更新
    await db.execute(
        update(models.Granary)
        .where(models.Granary.id == item_id)
        .values(**obj_in.model_dump(exclude={"code"})) # 工业常识：禁止通过此接口修改主键 code
    )
    await db.commit()
    await db.refresh(db_item)
    return db_item


# 🎯 接口 4：【删】- 依据 ID 删除廒间
@router.delete("/api/granary/{item_id}")
async def delete_granary(item_id: int, db: AsyncSession = Depends(get_db)):
    print('删除仓房信息')
    stmt = select(models.Granary).where(models.Granary.id == item_id)
    db_item = (await db.execute(stmt)).scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="未找到该廒间记录")
        
    await db.execute(delete(models.Granary).where(models.Granary.id == item_id))
    await db.commit()
    return {"status": "success", "msg": f"成功删除 ID 为 {item_id} 的廒间"}
