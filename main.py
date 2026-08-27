
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import uvicorn
from database import engine, SessionLocal, Base
from models import Item
from schemas import ItemCreate, ItemResponse, ItemUpdate
from crud import create_item, get_item, get_items, update_item, delete_item

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Python CRUD System", description="基于FastAPI和SQLAlchemy的增删改查示例")

# 依赖项：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/items/", response_model=ItemResponse, status_code=201)
def create_new_item(item: ItemCreate, db: Session = Depends(get_db)):
    """创建新项目"""
    return create_item(db=db, item=item)

@app.get("/items/", response_model=list[ItemResponse])
def read_all_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取所有项目，支持分页"""
    items = get_items(db, skip=skip, limit=limit)
    return items

@app.get("/items/{item_id}", response_model=ItemResponse)
def read_single_item(item_id: int, db: Session = Depends(get_db)):
    """获取单个项目"""
    db_item = get_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item

@app.put("/items/{item_id}", response_model=ItemResponse)
def update_existing_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    """更新项目"""
    db_item = update_item(db, item_id=item_id, item=item)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item

@app.delete("/items/{item_id}")
def delete_existing_item(item_id: int, db: Session = Depends(get_db)):
    """删除项目"""
    success = delete_item(db, item_id=item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Item deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
