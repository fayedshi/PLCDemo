from datetime import datetime
from typing import Optional, List
from fastapi import Depends
from sqlalchemy.future import select
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import VentilationMode
# 假设这是你的模型导入
# from models import AlarmLog 

class VentiConfigService:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_ventilation_modes(
        self,
        page: int = 1,
        size: int = 10
    ) -> List[VentilationMode]:
        """
        封装核心的数据库查询与业务筛选逻辑
        """
        # 计算需要跳过的条数
        offset = (page - 1) * size
        print('get modes list')
        # 1. 查询总条数（用于前端算总页数）
        # total = await self.session.query(VentilationMode).count()
        
        # 2. 查询当前页的实体数据
        # items = self.session.query(VentilationMode).offset(offset).limit(size).all()
        
        count_stmt = select(func.count()).select_from(VentilationMode)
        total = await self.session.scalar(count_stmt)  

        # data_query = select(VentilationMode).order_by(desc(VentilationMode.trigger_time))
        # if where_clauses:
        #     data_query = data_query.where(*where_clauses)    
        offset = (page - 1) * size        
        data_query = select(VentilationMode).offset(offset).limit(size)

        print('query ',data_query)
        # 4. 执行异步查询并返回结果
        data_result = await self.session.execute(data_query)
        items = data_result.scalars().all()
        return items, total