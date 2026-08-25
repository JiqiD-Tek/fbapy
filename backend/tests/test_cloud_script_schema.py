from backend.app.cloud.model.resource.script import CloudScript
from backend.app.cloud.schema.resource.script import CreateScriptParam, ScriptLine, UpdateScriptParam


def _build_script_payload() -> dict:
    return {
        'title': 'Bedtime Story',
        'content_type': 2,
        'toy_ids': [2, 1],
        'content': [
            ScriptLine(toy_id=1, text='Hello.').model_dump(mode='python'),
            ScriptLine(toy_id=2, text='Hi there.').model_dump(mode='python'),
        ],
    }


def test_create_script_param_defaults_device_id_and_favorite() -> None:
    obj = CreateScriptParam.model_validate(_build_script_payload())

    assert obj.device_id == 0
    assert obj.favorite == 0
    assert obj.content_type == 2
    assert obj.toy_ids == [1, 2]


def test_update_script_param_accepts_favorite_flag() -> None:
    obj = UpdateScriptParam.model_validate({'favorite': 1})

    assert obj.favorite == 1


def test_update_script_param_accepts_content_type() -> None:
    obj = UpdateScriptParam.model_validate({'content_type': 5})

    assert obj.content_type == 5


def test_cloud_script_model_has_favorite_column() -> None:
    favorite_column = CloudScript.__table__.columns.favorite
    content_type_column = CloudScript.__table__.columns.content_type

    assert favorite_column.default is not None
    assert favorite_column.default.arg == 0
    assert favorite_column.server_default is not None
    assert str(favorite_column.server_default.arg) == '0'
    assert favorite_column.comment == 'Favorite flag (0 no, 1 yes)'
    assert content_type_column.comment == '内容类型，1：语言 2：科学 3：社会 4：艺术 5：健康'
