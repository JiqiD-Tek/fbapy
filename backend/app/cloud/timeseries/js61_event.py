from __future__ import annotations

from backend.database.tsdb import TSDBBase, TSDBField


class JS61EventTable(TSDBBase):
    __tablename__ = 'js61_event'
    __columns__ = (
        TSDBField(name='ts', definition='TIMESTAMP', description='Event timestamp'),
        TSDBField(name='event_id', definition='VARCHAR(64) COMPOSITE KEY', description='Unique event id'),
        TSDBField(name='did', definition='VARCHAR(64)', description='device id'),
        TSDBField(name='direction', definition='VARCHAR(8)', description='Event direction, such as up/down'),
        TSDBField(name='category', definition='VARCHAR(32)', description='Business event category'),
        TSDBField(name='service', definition='VARCHAR(32)', description='Source service name'),
        TSDBField(name='topic', definition='VARCHAR(128)', description='Original message topic'),
        TSDBField(name='payload', definition='NCHAR(4096)', description='Original event payload'),
    )
    __tags__ = (
        TSDBField(name='baby_id', definition='VARCHAR(64)', description='Baby id'),
    )
