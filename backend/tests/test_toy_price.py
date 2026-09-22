import sqlalchemy as sa

from backend.app.cloud.model import Product, Toy, ToySeries
from backend.app.cloud.schema.device.toy import (
    CreateToyParam,
    CreateToySeriesParam,
    UpdateToySeriesParam,
)


def test_toy_models_no_longer_contain_commercial_price_fields() -> None:
    assert 'price' not in Toy.__table__.columns
    assert 'purchase_url' not in Toy.__table__.columns
    assert 'price' not in ToySeries.__table__.columns
    assert 'purchase_url' not in ToySeries.__table__.columns


def test_product_contains_commercial_price_fields() -> None:
    assert isinstance(Product.__table__.c.price.type, sa.BigInteger)
    assert Product.__table__.c.purchase_url.nullable is True


def test_toy_series_schemas_no_longer_expose_commercial_price_fields() -> None:
    assert 'price' not in CreateToySeriesParam.model_fields
    assert 'purchase_url' not in CreateToySeriesParam.model_fields
    assert 'price' not in UpdateToySeriesParam.model_fields
    assert 'purchase_url' not in UpdateToySeriesParam.model_fields
