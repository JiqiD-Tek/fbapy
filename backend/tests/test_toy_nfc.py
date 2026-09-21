import asyncio

from sqlalchemy import inspect

from backend.app.cloud.crud.crud_toy import toy_dao
from backend.app.cloud.model import Toy, ToyNfc
from backend.app.cloud.schema.device.toy import BatchCreateToyNfcParam, CreateToyParam, UpdateToyParam


class _ScalarResult:
    def scalar_one_or_none(self) -> None:
        return None


class _CapturingSession:
    statement = None

    async def execute(self, statement):  # noqa: ANN001, ANN201
        self.statement = statement
        return _ScalarResult()


def test_toy_does_not_automatically_load_nfc_bindings() -> None:
    assert 'nfc_bindings' not in inspect(Toy).relationships


def test_get_toy_by_nfc_code_joins_nfc_mapping_table() -> None:
    session = _CapturingSession()

    asyncio.run(
        toy_dao.get_by_nfc_code(
            session,  # type: ignore[arg-type]
            nfc_code='NFC-001',
            enabled_only=True,
        )
    )

    sql = str(session.statement)
    assert 'JOIN u_toy_nfc ON u_toy_nfc.toy_id = u_toy.id' in sql
    assert 'u_toy_nfc.nfc_code' in sql
    assert 'u_toy_nfc.status' in sql
    assert 'u_toy.status' in sql


def test_nfc_code_is_globally_unique() -> None:
    unique_constraints = {
        constraint.name
        for constraint in ToyNfc.__table__.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    }
    assert 'uq_toy_nfc_code' in unique_constraints


def test_toy_crud_schemas_do_not_own_nfc_code() -> None:
    assert 'nfc_code' not in Toy.__table__.columns
    assert 'nfc_code' not in CreateToyParam.model_fields
    assert 'nfc_code' not in UpdateToyParam.model_fields


def test_batch_nfc_param_deduplicates_codes() -> None:
    obj = BatchCreateToyNfcParam(
        toy_id=1,
        nfc_codes=[' NFC-001 ', 'NFC-001', 'NFC-002'],
        batch_no='2026-01',
    )
    assert obj.nfc_codes == ['NFC-001', 'NFC-002']
