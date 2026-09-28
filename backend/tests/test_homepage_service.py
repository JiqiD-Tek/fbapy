import asyncio

from backend.app.cloud.crud.crud_homepage import CRUDHomepage
from backend.app.cloud.model import Homepage
from backend.app.cloud.schema.homepage import HomepageDetail, HomepageType, UpdateHomepageParam


class FakeSession:
    def __init__(self) -> None:
        self.items = []

    def add(self, value) -> None:
        self.items.append(value)

    async def flush(self) -> None:
        return None


def test_create_homepage_config_accepts_json_array() -> None:
    db = FakeSession()

    config = asyncio.run(
        CRUDHomepage(Homepage).create_config(
            db,
            HomepageType.banner,
            [{'picture': '', 'href': ''}],
        )
    )

    assert config.config_type == 'banner'
    assert config.content == [{'picture': '', 'href': ''}]
    assert db.items == [config]


def test_homepage_detail_can_be_built_from_update_param() -> None:
    obj = UpdateHomepageParam(
        banner=[{'picture': '', 'href': ''}],
        newest=[],
        featured=[],
    )

    detail = HomepageDetail(**obj.model_dump())

    assert detail.banner == [{'picture': '', 'href': ''}]
