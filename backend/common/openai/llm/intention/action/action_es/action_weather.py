# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : tst_action_weather.py
@Author  : guhua@jiqid.com
@Date    : 2025/05/28 19:55
"""

from backend.common.openai.llm.intention.action.action_en.action_weather import ActionWeather as Action


class ActionWeather(Action):
    """天气查询工具（支持实时数据口语化播报）"""

    @property
    def system_prompt(self) -> str:
        return """Plantilla de Instrucciones para el Informe Meteorológico

        Directrices de Datos:
        - Usar únicamente datos crudos de la API; no inferir ni complementar datos faltantes.
        - Marcar datos faltantes como "No disponible".
        - Unidades: Temperatura en Celsius ("de baja a alta", p. ej., "10 a 25 grados"), velocidad del viento en niveles (p. ej., "Nivel 3 a 4"), dirección del viento en términos cardinales (p. ej., "Viento noreste").

        Plantilla de Informe:
        Informe meteorológico de {Lugar} para {Fecha}:
        - Temperatura: {Temperatura}
        - Condición: {Condición Meteorológica}
        - Viento: Nivel {Velocidad del Viento} {Dirección del Viento}
        Consejo: {Consejo de Vida}

        Manejo de Errores:
        - Datos Faltantes: "No se pudo obtener {Datos Faltantes} para {Lugar}. Intenta de nuevo más tarde."
        - Clima Extremo: "Alerta: {Contenido de la Alerta}. Recomendado: {Medidas de Protección}."

        Acciones Prohibidas:
        - Usar términos crudos de la API (p. ej., "moderate rain").
        - Mencionar horarios específicos (p. ej., "14:30").
        - Incluir consejos no verificados o fórmulas de cálculo.
        """
