from __future__ import annotations

import re

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from openai import AsyncAzureOpenAI

from backend.app.led.prompt import (
    build_code_prompt,
    build_design_prompt,
    build_fast_generation_prompt,
    parse_code_response,
    parse_design_response,
    parse_fast_generation_response,
)
from backend.app.led.schema.domain import SemanticDesign, build_spec_from_design
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
class GenerationResult:
    design: SemanticDesign
    function_code: str


@dataclass(frozen=True)
class FastGenerationResult:
    design: SemanticDesign
    function_code: str
    mode: str


@dataclass(frozen=True)
class TwoStageGenerationRuntime:
    client: AsyncAzureOpenAI
    model: str
    store_response: bool = False

    async def generate_design(self, description: str) -> SemanticDesignResult:
        stage = await self._run_stage(
            stage_name='DESIGN',
            prompt=build_design_prompt(description),
            schema=DESIGN_RESPONSE_SCHEMA,
        )
        return SemanticDesignResult(
            design=parse_design_response(stage.response_text),
        )

    async def generate_code(self, design: SemanticDesign) -> FunctionGenerationResult:
        stage = await self._run_stage(
            stage_name='CODE',
            prompt=build_code_prompt(design),
            schema=CODE_RESPONSE_SCHEMA,
        )
        function_code = parse_code_response(stage.response_text)
        build_spec_from_design(design, function_code)
        return FunctionGenerationResult(
            function_code=function_code,
        )

    async def generate(self, description: str) -> GenerationResult:
        design_result = await self.generate_design(description)
        function_result = await self.generate_code(design_result.design)
        return GenerationResult(
            design=design_result.design,
            function_code=function_result.function_code,
        )

    async def generate_fast(
        self,
        description: str,
        *,
        fallback_to_two_stage: bool = True,
    ) -> FastGenerationResult:
        normalized_description = str(description or '').strip()
        if not normalized_description:
            raise ValueError('description must not be empty')

        if fallback_to_two_stage and _should_fallback_to_two_stage(normalized_description):
            fallback_result = await self.generate(normalized_description)
            return FastGenerationResult(
                design=fallback_result.design,
                function_code=fallback_result.function_code,
                mode='two_stage_fallback',
            )

        try:
            stage = await self._run_stage(
                stage_name='FAST',
                prompt=build_fast_generation_prompt(normalized_description),
                schema=FAST_RESPONSE_SCHEMA,
            )
            design, function_code = parse_fast_generation_response(stage.response_text)
            build_spec_from_design(design, function_code)
            return FastGenerationResult(
                design=design,
                function_code=function_code,
                mode='single_pass',
            )
        except ValueError:
            if not fallback_to_two_stage:
                raise
            fallback_result = await self.generate(normalized_description)
            return FastGenerationResult(
                design=fallback_result.design,
                function_code=fallback_result.function_code,
                mode='two_stage_fallback',
            )

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
                store=self.store_response,
            )
        except Exception as exc:
            log.error(f'LED {stage_name} request failed: {exc}')
            raise errors.GatewayError(msg=f'Azure OpenAI request failed: {exc}') from exc

        response_text = _extract_response_text(response)
        return GenerationStageResult(response_text=response_text)


class LedService:
    async def generate_semantic_design(
        self,
        *,
        description: str,
        model: str | None = None,
        store_response: bool = False,
    ) -> dict[str, Any]:
        return await self._run(
            model=model,
            store_response=store_response,
            action=lambda runtime: self._generate_semantic_design(runtime, description=description),
        )

    async def generate_function_from_design(
        self,
        *,
        design: SemanticDesign,
        model: str | None = None,
        store_response: bool = False,
    ) -> dict[str, Any]:
        return await self._run(
            model=model,
            store_response=store_response,
            action=lambda runtime: self._generate_function_code(runtime, design=design),
        )

    async def generate_animation(
        self,
        *,
        description: str,
        model: str | None = None,
        store_response: bool = False,
    ) -> dict[str, Any]:
        return await self._run(
            model=model,
            store_response=store_response,
            action=lambda runtime: self._generate_led_animation(runtime, description=description),
        )

    async def generate_animation_fast(
        self,
        *,
        description: str,
        model: str | None = None,
        store_response: bool = False,
        fallback_to_two_stage: bool = True,
    ) -> dict[str, Any]:
        return await self._run(
            model=model,
            store_response=store_response,
            action=lambda runtime: self._generate_led_animation_fast(
                runtime,
                description=description,
                fallback_to_two_stage=fallback_to_two_stage,
            ),
        )

    @staticmethod
    def _build_runtime(*, model: str | None, store_response: bool) -> TwoStageGenerationRuntime:
        resolved_model = (
            str(model or '').strip()
            or str(settings.AZURE_OPENAI_MODEL or '').strip()
            or DEFAULT_AZURE_OPENAI_MODEL
        )
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
            model=resolved_model,
            store_response=store_response,
        )

    @staticmethod
    async def _generate_semantic_design(
        runtime: TwoStageGenerationRuntime,
        *,
        description: str,
    ) -> dict[str, Any]:
        result = await runtime.generate_design(description)
        return {
            'semantic_design': result.design.to_dict(),
        }

    @staticmethod
    async def _generate_function_code(
        runtime: TwoStageGenerationRuntime,
        *,
        design: SemanticDesign,
    ) -> dict[str, Any]:
        result = await runtime.generate_code(design)
        return {
            'function_code': result.function_code,
        }

    @staticmethod
    async def _generate_led_animation(
        runtime: TwoStageGenerationRuntime,
        *,
        description: str,
    ) -> dict[str, Any]:
        result = await runtime.generate(description)
        return {
            'semantic_design': result.design.to_dict(),
            'function_code': result.function_code,
        }

    @staticmethod
    async def _generate_led_animation_fast(
        runtime: TwoStageGenerationRuntime,
        *,
        description: str,
        fallback_to_two_stage: bool,
    ) -> dict[str, Any]:
        result = await runtime.generate_fast(
            description,
            fallback_to_two_stage=fallback_to_two_stage,
        )
        return {
            'mode': result.mode,
            'semantic_design': result.design.to_dict(),
            'function_code': result.function_code,
        }

    async def _run(
        self,
        *,
        model: str | None,
        store_response: bool,
        action: Callable[[TwoStageGenerationRuntime], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        runtime = self._build_runtime(model=model, store_response=store_response)
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


FAST_RESPONSE_SCHEMA = StructuredOutputSchema(
    name='led_animation_fast_generation',
    schema={
        'type': 'object',
        'properties': {
            'semantic_design': DESIGN_RESPONSE_SCHEMA.schema,
            'function_code': {'type': 'string', 'minLength': 1},
        },
        'required': ['semantic_design', 'function_code'],
        'additionalProperties': False,
    },
)
def _should_fallback_to_two_stage(description: str) -> bool:
    text = str(description or '').strip()
    if not text:
        return False

    cjk_units = re.findall(r'[\u3400-\u9fff]', text)
    if cjk_units:
        compact = re.sub(
            r"[\s,.;:!?\u3001\u3002\uff01\uff1f\uff1b\uff1a\\()\uff08\uff09\"'\u2018\u2019\u201c\u201d-]+",
            '',
            text,
        )
        return len(compact) <= 8

    words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", text)
    return len(words) <= 3 and len(text) <= 24


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
    'FastGenerationResult',
    'FunctionGenerationResult',
    'GenerationResult',
    'LedService',
    'SemanticDesignResult',
    'StructuredOutputSchema',
    'led_service',
]
