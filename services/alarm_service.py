from datetime import datetime
from typing import Optional, List
from fastapi import Depends
from sqlalchemy.future import select
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AlarmLog
# 假设这是你的模型导入
# from models import AlarmLog 

class AlarmService:
    def __init__(self, session:AsyncSession = Depends(get_db)):
        self.session = session

    async def get_history(
        self,
        house_code: Optional[int] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        size: int = 10
    ) -> List[AlarmLog]:
        """
        封装核心的数据库查询与业务筛选逻辑
        """
        
        # 2. 动态组装筛选条件
        where_clauses = []
        if house_code is not None:
            where_clauses.append(AlarmLog.house_id == house_code)
        if severity is not None:
            where_clauses.append(AlarmLog.severity == severity)
        if start_time is not None:
            where_clauses.append(AlarmLog.time >= start_time)
        if end_time is not None:
            where_clauses.append(AlarmLog.time <= end_time)

        
        # 2. 异步计算总条数 (Total) —— 不加 limit 和 offset
        count_query = select(func.count()).select_from(AlarmLog)
        if where_clauses:
            count_query = count_query.where(*where_clauses)
        
        count_result = await self.session.execute(count_query)
        history_total = count_result.scalar_one()  # 🎯 拿到总条数

        # 3. 分页处理
        # 1. 构建基础查询语句
        data_query = select(AlarmLog).order_by(desc(AlarmLog.time))
        if where_clauses:
            data_query = data_query.where(*where_clauses)    
        offset = (page - 1) * size        
        data_query = data_query.offset(offset).limit(size)

        print('query ',data_query)
        # 4. 执行异步查询并返回结果
        data_result = await self.session.execute(data_query)
        alarms= data_result.scalars().all()
        return alarms, history_total

