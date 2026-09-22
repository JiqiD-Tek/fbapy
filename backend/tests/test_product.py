from sqlalchemy import inspect

from backend.app.cloud.model import Product
from backend.app.cloud.schema.device.product import CreateProductParam, UpdateProductParam


def test_product_uses_one_level_parent_reference() -> None:
    parent_id = Product.__table__.c.parent_id
    foreign_keys = {foreign_key.target_fullname for foreign_key in parent_id.foreign_keys}

    assert foreign_keys == {'u_product.id'}
    assert parent_id.nullable is True
    assert 'parent' not in inspect(Product).relationships


def test_product_reference_is_required() -> None:
    assert Product.__table__.c.ref_id.nullable is False
    assert CreateProductParam.model_fields['ref_id'].is_required()


def test_create_product_accepts_series_parent_and_toy_child() -> None:
    parent = CreateProductParam(
        ref_type='toy_series',
        ref_id=1,
        name='森林伙伴系列',
        price=29900,
    )
    child = CreateProductParam(
        parent_id=10,
        ref_type='toy',
        ref_id=2,
        name='小熊玩偶',
        price=9900,
    )

    assert parent.parent_id is None
    assert child.parent_id == 10


def test_update_product_can_explicitly_clear_parent() -> None:
    obj = UpdateProductParam(parent_id=None)

    assert obj.model_dump(exclude_unset=True) == {'parent_id': None}
