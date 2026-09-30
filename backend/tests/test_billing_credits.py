from decimal import Decimal

import pytest

from backend.app.cloud.schema.billing import CreditUsageType
from backend.app.cloud.service.billing_service import BillingService, CreditCalculator


def test_build_session_id_is_stable_and_fits_column() -> None:
    biz_id = '2a367799a1ec42e08d8dfbe21569fe90:tts:tts_709972eb4a9f4876a201d4e0763b7aaa'

    session_id = BillingService._build_session_id(
        biz_type='STORY',
        biz_id=biz_id,
    )

    assert session_id == BillingService._build_session_id(
        biz_type='STORY',
        biz_id=biz_id,
    )
    assert session_id.startswith('story:')
    assert len(session_id) <= 64


def test_yuan_and_credits_conversion() -> None:
    assert CreditCalculator.yuan_to_credits(10) == 100_000_000
    assert CreditCalculator.yuan_to_credits('0.0000001') == 1
    assert CreditCalculator.credits_to_yuan(100_000_000) == Decimal('10.0000000')


def test_mini_credits_conversion_rounds_up_to_whole_credit() -> None:
    assert CreditCalculator.llm_input(0) == 0
    assert CreditCalculator.llm_input(1) == 1
    assert CreditCalculator.llm_input(1000) == 3
    assert CreditCalculator.llm_output(1) == 1
    assert CreditCalculator.llm_output(1000) == 30


def test_tts_and_asr_credits_conversion() -> None:
    assert CreditCalculator.tts(100) == 300
    assert CreditCalculator.asr(0) == 0
    assert CreditCalculator.asr(1) == 12_500
    assert CreditCalculator.asr(0.1) == 1_250
    assert CreditCalculator.asr(3600) == 45_000_000


def test_calculate_credits_from_raw_usage() -> None:
    assert CreditCalculator.calculate(
        usage_type=CreditUsageType.LLM_INPUT_CHARACTERS,
        quantity=1000,
    ) == 3
    assert CreditCalculator.calculate(
        usage_type=CreditUsageType.LLM_OUTPUT_CHARACTERS,
        quantity=1000,
    ) == 30
    assert CreditCalculator.calculate(
        usage_type=CreditUsageType.TTS_CHARACTERS,
        quantity=100,
    ) == 300
    assert CreditCalculator.calculate(
        usage_type=CreditUsageType.ASR_SECONDS,
        quantity=1,
    ) == 12_500


def test_calculate_rejects_fractional_count() -> None:
    with pytest.raises(ValueError, match='非负整数'):
        CreditCalculator.calculate(
            usage_type=CreditUsageType.TTS_CHARACTERS,
            quantity=1.5,
        )


@pytest.mark.parametrize(
    ('convert', 'value'),
    [
        (CreditCalculator.yuan_to_credits, -1),
        (CreditCalculator.credits_to_yuan, -1),
        (CreditCalculator.llm_input, -1),
        (CreditCalculator.llm_output, -1),
        (CreditCalculator.tts, -1),
        (CreditCalculator.asr, -1),
    ],
)
def test_credits_conversion_rejects_negative_usage(convert, value: int) -> None:  # noqa: ANN001
    with pytest.raises(ValueError):
        convert(value)
