from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

import httpx
from openai import AsyncAzureOpenAI

from backend.app.cloud.service.led.domain import (
    ALLOWED_COMPLEXITY_LEVELS,
    LedAnimationSpec,
    SUPPORTED_RENDER_STRATEGIES,
    SUPPORTED_SUBJECT_FAMILIES,
    SUPPORTED_SYMMETRY_MODES,
    SUPPORTED_TOPOLOGIES,
    SemanticDesign,
    build_spec_from_design,
    validate_function_code,
)
from backend.app.cloud.service.led.prompt import (
    build_code_prompt,
    build_design_prompt,
    parse_code_response,
    parse_design_response,
)
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings

DEFAULT_AZURE_OPENAI_MODEL = 'gpt-5.4'
DEFAULT_AZURE_OPENAI_API_VERSION = '2025-03-01-preview'
HTTP_TIMEOUT = httpx.Timeout(connect=15.0, read=180.0, write=30.0, pool=30.0)
HTTP_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=120.0)


@dataclass(frozen=True)
class StructuredOutputSchema:
    name: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class GenerationResult:
    model: str
    semantic_design: SemanticDesign
    function_code: str
    animation_spec: LedAnimationSpec


@dataclass(frozen=True)
class TwoStageGenerationRuntime:
    client: AsyncAzureOpenAI
    model: str

    async def generate_design(self, description: str) -> SemanticDesign:
        response_text = await self._run_stage(
            stage_name='DESIGN',
            prompt=build_design_prompt(description),
            schema=DESIGN_RESPONSE_SCHEMA,
        )
        return _bind_raw_user_request(parse_design_response(response_text), description)

    async def generate_code(self, design: SemanticDesign) -> str:
        response_text = await self._run_stage(
            stage_name='CODE',
            prompt=build_code_prompt(design),
            schema=CODE_RESPONSE_SCHEMA,
        )
        return validate_function_code(parse_code_response(response_text))

    async def generate(self, description: str) -> GenerationResult:
        design = await self.generate_design(description)
        function_code = await self.generate_code(design)
        return GenerationResult(
            model=self.model,
            semantic_design=design,
            function_code=function_code,
            animation_spec=build_spec_from_design(design, function_code),
        )

    async def _run_stage(
            self,
            *,
            stage_name: str,
            prompt: str,
            schema: StructuredOutputSchema,
    ) -> str:
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=prompt,
                text={
                    'format': {
                        'type': 'json_schema',
                        'name': schema.name,
                        'strict': True,
                        'schema': schema.schema,
                    }
                },
                store=False,
            )
        except Exception as exc:
            log.error(f'LED {stage_name} request failed: {exc}')
            raise errors.GatewayError(msg=f'Azure OpenAI request failed: {exc}') from exc

        return _extract_response_text(response)


class LedService:
    async def generate_semantic_design(
            self,
            *,
            description: str,
    ) -> dict[str, Any]:
        design = await self._run(action=lambda runtime: runtime.generate_design(description))
        return design.to_dict()

    async def generate_function_from_design(
            self,
            *,
            design: SemanticDesign,
    ) -> dict[str, Any]:
        function_code = await self._run(action=lambda runtime: runtime.generate_code(design))
        return {'function_code': function_code}

    async def generate_animation(
            self,
            *,
            description: str,
    ) -> dict[str, Any]:
        result = await self._run(action=lambda runtime: runtime.generate(description))
        return {
            'model': result.model,
            'semantic_design': result.semantic_design.to_dict(),
            'function_code': result.function_code,
            'animation_spec': result.animation_spec.to_dict(),
        }

    async def _run(
            self,
            *,
            action: Callable[[TwoStageGenerationRuntime], Awaitable[Any]],
    ) -> Any:
        runtime = self._build_runtime()
        try:
            return await action(runtime)
        except (errors.RequestError, errors.ServerError, errors.GatewayError):
            raise
        except ValueError as exc:
            raise errors.RequestError(msg=str(exc)) from exc
        finally:
            await _close_client(runtime.client)

    @staticmethod
    def _build_runtime() -> TwoStageGenerationRuntime:
        model_name = str(settings.AZURE_OPENAI_MODEL or '').strip() or DEFAULT_AZURE_OPENAI_MODEL
        endpoint = str(settings.AZURE_OPENAI_ENDPOINT or '').strip()
        subscription_key = settings.AZURE_OPENAI_SUBSCRIPTION_KEY.get_secret_value().strip()
        api_version = str(settings.AZURE_OPENAI_API_VERSION or '').strip() or DEFAULT_AZURE_OPENAI_API_VERSION

        if not endpoint:
            raise errors.ServerError(msg='AZURE_OPENAI_ENDPOINT is not configured')
        if not subscription_key:
            raise errors.ServerError(msg='AZURE_OPENAI_SUBSCRIPTION_KEY is not configured')

        client = AsyncAzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=subscription_key,
            http_client=httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
                limits=HTTP_LIMITS,
            ),
        )
        return TwoStageGenerationRuntime(client=client, model=model_name)


def _string_array_schema(*, min_items: int) -> dict[str, Any]:
    return {
        'type': 'array',
        'minItems': min_items,
        'items': {'type': 'string', 'minLength': 1},
    }


def _mapping_array_schema(*, keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        'type': 'object',
        'properties': {key: _string_array_schema(min_items=2) for key in keys},
        'required': list(keys),
        'additionalProperties': False,
    }


def _enum_schema(*, values: tuple[str, ...]) -> dict[str, Any]:
    return {
        'type': 'string',
        'enum': list(values),
    }


def _layout_constraints_schema() -> dict[str, Any]:
    return {
        'type': 'object',
        'properties': {
            'subject_min_pixels': {'type': 'integer', 'minimum': 1},
            'subject_max_pixels': {'type': 'integer', 'minimum': 1},
            'supporting_max_pixels': {'type': 'integer', 'minimum': 0},
            'background_max_pixels': {'type': 'integer', 'minimum': 0},
            'bright_max_pixels': {'type': 'integer', 'minimum': 1},
            'max_centroid_shift': {'type': 'integer', 'minimum': 0},
            'stable_regions': _string_array_schema(min_items=2),
            'reactive_regions': _string_array_schema(min_items=1),
        },
        'required': [
            'subject_min_pixels',
            'subject_max_pixels',
            'supporting_max_pixels',
            'background_max_pixels',
            'bright_max_pixels',
            'max_centroid_shift',
            'stable_regions',
            'reactive_regions',
        ],
        'additionalProperties': False,
    }


DESIGN_RESPONSE_SCHEMA = StructuredOutputSchema(
    name='led_animation_semantic_design',
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'minLength': 1},
            'raw_user_request': {'type': 'string', 'minLength': 1},
            'expanded_request': {'type': 'string', 'minLength': 1},
            'summary': {'type': 'string', 'minLength': 1},
            'subject_family': _enum_schema(values=SUPPORTED_SUBJECT_FAMILIES),
            'topology': _enum_schema(values=SUPPORTED_TOPOLOGIES),
            'render_strategy': _enum_schema(values=SUPPORTED_RENDER_STRATEGIES),
            'symmetry_mode': _enum_schema(values=SUPPORTED_SYMMETRY_MODES),
            'canonical_view': {'type': 'string', 'minLength': 1},
            'shape_anchors': {
                'type': 'array',
                'minItems': 2,
                'maxItems': 4,
                'items': {'type': 'string', 'minLength': 1},
            },
            'complexity': _enum_schema(values=ALLOWED_COMPLEXITY_LEVELS),
            'subject': {'type': 'string', 'minLength': 1},
            'color_palette': _string_array_schema(min_items=2),
            'composition': _string_array_schema(min_items=2),
            'motion_rules': _string_array_schema(min_items=3),
            'energy_mapping': _mapping_array_schema(keys=('low', 'medium', 'high')),
            'audio_feature_mapping': _mapping_array_schema(
                keys=('energy', 'bass', 'mid', 'high', 'onset')
            ),
            'layout_constraints': _layout_constraints_schema(),
            'avoid_list': _string_array_schema(min_items=2),
            'implementation_hints': _string_array_schema(min_items=3),
        },
        'required': [
            'name',
            'raw_user_request',
            'expanded_request',
            'summary',
            'subject_family',
            'topology',
            'render_strategy',
            'symmetry_mode',
            'canonical_view',
            'shape_anchors',
            'complexity',
            'subject',
            'color_palette',
            'composition',
            'motion_rules',
            'energy_mapping',
            'audio_feature_mapping',
            'layout_constraints',
            'avoid_list',
            'implementation_hints',
        ],
        'additionalProperties': False,
    },
)

CODE_RESPONSE_SCHEMA = StructuredOutputSchema(
    name='led_animation_function_code',
    schema={
        'type': 'object',
        'properties': {
            'function_code': {'type': 'string', 'minLength': 1},
        },
        'required': ['function_code'],
        'additionalProperties': False,
    },
)


def _response_get(response: Any, name: str) -> Any:
    if isinstance(response, dict):
        return response.get(name)
    return getattr(response, name, None)


def _extract_response_text(response: Any) -> str:
    output_text = _response_get(response, 'output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    fragments = [fragment.strip() for fragment in _iter_output_text_fragments(_response_get(response, 'output'))]
    fragments = [fragment for fragment in fragments if fragment]
    if fragments:
        return '\n'.join(fragments)

    raise ValueError('OpenAI response does not contain output_text')


def _iter_output_text_fragments(output: Any) -> list[str]:
    if not isinstance(output, (list, tuple)):
        return []

    fragments: list[str] = []
    for item in output:
        content = item.get('content') if isinstance(item, dict) else getattr(item, 'content', None)
        if not isinstance(content, (list, tuple)):
            continue
        for part in content:
            part_type = part.get('type') if isinstance(part, dict) else getattr(part, 'type', None)
            text = _extract_output_text_part(part)
            if part_type == 'output_text' and text:
                fragments.append(text)
    return fragments


def _extract_output_text_part(part: Any) -> str:
    text = part.get('text') if isinstance(part, dict) else getattr(part, 'text', None)
    if isinstance(text, str):
        return text
    if isinstance(text, dict):
        return str(text.get('value') or '').strip()
    return str(getattr(text, 'value', '') or '').strip()


def _bind_raw_user_request(design: SemanticDesign, raw_user_request: str) -> SemanticDesign:
    normalized_raw_user_request = str(raw_user_request or '').strip()
    if not normalized_raw_user_request:
        raise ValueError('raw_user_request must not be empty')
    bound_design = replace(design, raw_user_request=normalized_raw_user_request)
    bound_design.validate()
    return bound_design


async def _close_client(client: AsyncAzureOpenAI) -> None:
    try:
        await client.close()
    except Exception as exc:
        log.error(f'LED client close failed: {exc}')


led_service = LedService()

__all__ = ['LedService', 'led_service']
