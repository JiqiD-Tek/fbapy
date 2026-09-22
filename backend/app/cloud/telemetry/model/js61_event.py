from __future__ import annotations

from backend.database.tsdb import TSDBBase, TSDBField


class JS61EventTable(TSDBBase):
    """JS61 舞台事件时序表。"""

    __tablename__ = 'js61_event'
    __columns__ = (
        TSDBField(name='ts', definition='TIMESTAMP', description='事件时间'),
        TSDBField(name='event_id', definition='VARCHAR(64) COMPOSITE KEY', description='事件唯一 ID'),
        TSDBField(name='did', definition='VARCHAR(64)', description='设备 ID'),
        TSDBField(name='category', definition='VARCHAR(32)', description='业务事件类别'),
        TSDBField(name='service', definition='VARCHAR(32)', description='来源服务名称'),
        TSDBField(name='topic', definition='VARCHAR(128)', description='原始消息主题'),
        TSDBField(name='toy_ids', definition='NCHAR(256)', description='本次事件选择的玩偶 ID 索引字符串'),
        TSDBField(name='payload', definition='NCHAR(4096)', description='原始事件载荷'),
    )
    __tags__ = (
        TSDBField(name='baby_id', definition='VARCHAR(64)', description='宝宝 ID'),
    )
