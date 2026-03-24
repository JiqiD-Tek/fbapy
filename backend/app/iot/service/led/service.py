from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from openai import AsyncAzureOpenAI

from backend.app.iot.service.led.domain import SemanticDesign, build_spec_from_design
from backend.app.iot.service.led.prompt import (
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


@dataclass(frozen=True)
class StructuredOutputSchema:
    name: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class GenerationStageResult:
    response_text: str


@dataclass(frozen=True)
class SemanticDesignResult:
    design: SemanticDesign


@dataclass(frozen=True)
class FunctionGenerationResult:
    function_code: str


@dataclass(frozen=True)
class TwoStageGenerationRuntime:
    client: AsyncAzureOpenAI
    model: str

    async def generate_design(self, description: str) -> SemanticDesignResult:
        stage = await self._run_stage(
            stage_name='DESIGN',
            prompt=build_design_prompt(description),
            schema=DESIGN_RESPONSE_SCHEMA,
        )
        return SemanticDesignResult(design=parse_design_response(stage.response_text))

    async def generate_code(self, design: SemanticDesign) -> FunctionGenerationResult:
        stage = await self._run_stage(
            stage_name='CODE',
            prompt=build_code_prompt(design),
            schema=CODE_RESPONSE_SCHEMA,
        )
        function_code = parse_code_response(stage.response_text)
        build_spec_from_design(design, function_code)
        return FunctionGenerationResult(function_code=function_code)

    async def generate(self, description: str) -> FunctionGenerationResult:
        design_result = await self.generate_design(description)
        return await self.generate_code(design_result.design)

    async def _run_stage(
        self,
        *,
        stage_name: str,
        prompt: str,
        schema: StructuredOutputSchema,
    ) -> GenerationStageResult:
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

        return GenerationStageResult(response_text=_extract_response_text(response))


class LedService:
    async def generate_semantic_design(
        self,
        *,
        description: str,
    ) -> dict[str, Any]:
        return await self._run(
            action=lambda runtime: self._generate_semantic_design(runtime, description=description),
        )

    async def generate_function_from_design(
        self,
        *,
        design: SemanticDesign,
    ) -> dict[str, Any]:
        return await self._run(
            action=lambda runtime: self._generate_function_code(runtime, design=design),
        )

    async def generate_animation(
        self,
        *,
        description: str,
    ) -> dict[str, Any]:
        return await self._run(
            action=lambda runtime: self._generate_animation(runtime, description=description),
        )

    @staticmethod
    def _build_runtime() -> TwoStageGenerationRuntime:
        model_name = str(settings.AZURE_OPENAI_MODEL or '').strip() or DEFAULT_AZURE_OPENAI_MODEL
        endpoint = str(settings.AZURE_OPENAI_ENDPOINT or '').strip()
        api_key = settings.AZURE_OPENAI_SUBSCRIPTION_KEY.get_secret_value().strip()
        api_version = str(settings.AZURE_OPENAI_API_VERSION or '').strip() or DEFAULT_AZURE_OPENAI_API_VERSION

        if not endpoint:
            raise errors.ServerError(msg='AZURE_OPENAI_ENDPOINT is not configured')
        if not api_key:
            raise errors.ServerError(msg='AZURE_OPENAI_SUBSCRIPTION_KEY is not configured')

        client = AsyncAzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15.0, read=180.0, write=30.0, pool=30.0),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=120.0),
            ),
        )
        return TwoStageGenerationRuntime(
            client=client,
            model=model_name,
        )

    @staticmethod
    async def _generate_semantic_design(
        runtime: TwoStageGenerationRuntime,
        *,
        description: str,
    ) -> dict[str, Any]:
        result = await runtime.generate_design(description)
        return result.design.to_dict()

    @staticmethod
    async def _generate_function_code(
        runtime: TwoStageGenerationRuntime,
        *,
        design: SemanticDesign,
    ) -> dict[str, Any]:
        result = await runtime.generate_code(design)
        return {'function_code': result.function_code}

    @staticmethod
    async def _generate_animation(
        runtime: TwoStageGenerationRuntime,
        *,
        description: str,
    ) -> dict[str, Any]:
        result = await runtime.generate(description)
        return {'function_code': result.function_code}

    async def _run(
        self,
        *,
        action: Callable[[TwoStageGenerationRuntime], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        runtime = self._build_runtime()
        try:
            return await action(runtime)
        except (errors.RequestError, errors.ServerError, errors.GatewayError):
            raise
        except ValueError as exc:
            raise errors.RequestError(msg=str(exc)) from exc
        finally:
            await _close_client(runtime.client)


DESIGN_RESPONSE_SCHEMA = StructuredOutputSchema(
    name='led_animation_semantic_design',
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'minLength': 1},
            'user_request': {'type': 'string', 'minLength': 1},
            'summary': {'type': 'string', 'minLength': 1},
            'subject': {'type': 'string', 'minLength': 1},
            'color_palette': {
                'type': 'array',
                'minItems': 2,
                'items': {'type': 'string', 'minLength': 1},
            },
            'composition': {
                'type': 'array',
                'minItems': 2,
                'items': {'type': 'string', 'minLength': 1},
            },
            'motion_rules': {
                'type': 'array',
                'minItems': 3,
                'items': {'type': 'string', 'minLength': 1},
            },
            'energy_mapping': {
                'type': 'object',
                'properties': {
                    'low': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'medium': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'high': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                },
                'required': ['low', 'medium', 'high'],
                'additionalProperties': False,
            },
            'audio_feature_mapping': {
                'type': 'object',
                'properties': {
                    'energy': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'bass': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'mid': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'high': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                    'onset': {
                        'type': 'array',
                        'minItems': 2,
                        'items': {'type': 'string', 'minLength': 1},
                    },
                },
                'required': ['energy', 'bass', 'mid', 'high', 'onset'],
                'additionalProperties': False,
            },
            'avoid_list': {
                'type': 'array',
                'minItems': 2,
                'items': {'type': 'string', 'minLength': 1},
            },
            'implementation_hints': {
                'type': 'array',
                'minItems': 3,
                'items': {'type': 'string', 'minLength': 1},
            },
        },
        'required': [
            'name',
            'user_request',
            'summary',
            'subject',
            'color_palette',
            'composition',
            'motion_rules',
            'energy_mapping',
            'audio_feature_mapping',
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


async def _close_client(client: AsyncAzureOpenAI) -> None:
    try:
        await client.close()
    except Exception as exc:
        log.error(f'LED client close failed: {exc}')


led_service: LedService = LedService()


__all__ = [
    'FunctionGenerationResult',
    'LedService',
    'SemanticDesignResult',
    'StructuredOutputSchema',
    'led_service',
]
