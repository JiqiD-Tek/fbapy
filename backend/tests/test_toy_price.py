import pytest

import sqlalchemy as sa

from pydantic import ValidationError

from backend.app.cloud.model import Toy, ToySeries
from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    CreateToySeriesParam,
    UpdateToyParam,
    UpdateToySeriesParam,
)


@pytest.mark.parametrize('model', [ToySeries, Toy])
def test_toy_price_columns_allow_unset_fen_amounts(model: type[ToySeries] | type[Toy]) -> None:
    column = model.__table__.c.price

    assert isinstance(column.type, sa.BigInteger)
    assert column.nullable is True


@pytest.mark.parametrize(
    ('schema', 'valid_kwargs'),
    [
        (CreateToySeriesParam, {'name': 'Series', 'price': 1}),
        (CreateToySeriesParam, {'name': 'Series'}),
        (CreateToySeriesParam, {'name': 'Series', 'price': None}),
        (CreateToyParam, {'name': 'Toy', 'system_prompt': 'Prompt', 'price': 1}),
        (CreateToyParam, {'name': 'Toy', 'system_prompt': 'Prompt'}),
        (CreateToyParam, {'name': 'Toy', 'system_prompt': 'Prompt', 'price': None}),
    ],
)
def test_create_toy_price_accepts_positive_integer_or_unset(schema: type, valid_kwargs: dict[str, object]) -> None:
    value = schema(**valid_kwargs)
    assert value.price == valid_kwargs.get('price')


@pytest.mark.parametrize('schema', [UpdateToySeriesParam, UpdateToyParam])
def test_update_toy_price_accepts_unset(schema: type) -> None:
    assert schema(price=None).price is None


@pytest.mark.parametrize(
    ('schema', 'kwargs'),
    [
        (CreateToySeriesParam, {'name': 'Series', 'price': 0}),
        (CreateToySeriesParam, {'name': 'Series', 'price': -1}),
        (CreateToyParam, {'name': 'Toy', 'system_prompt': 'Prompt', 'price': 0}),
        (CreateToyParam, {'name': 'Toy', 'system_prompt': 'Prompt', 'price': -1}),
        (UpdateToySeriesParam, {'price': 0}),
        (UpdateToySeriesParam, {'price': -1}),
        (UpdateToyParam, {'price': 0}),
        (UpdateToyParam, {'price': -1}),
    ],
)
def test_toy_price_rejects_non_positive_values(schema: type, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        schema(**kwargs)
