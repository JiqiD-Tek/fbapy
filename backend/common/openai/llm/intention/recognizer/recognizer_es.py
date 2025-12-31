# -*- coding: UTF-8 -*-
"""
@Project : jiqid-py
@File    : recognizer_es.py
@Author  : guhua@jiqid.com
@Date    : 2025/06/14 10:59
"""

from typing import Any, Dict

from backend.common.openai.llm.intention.action.action_es.action_alarm import ActionAlarm
from backend.common.openai.llm.intention.action.action_es.action_control import ActionControl
from backend.common.openai.llm.intention.action.action_es.action_music import ActionMusic
from backend.common.openai.llm.intention.action.action_es.action_news import ActionNews
from backend.common.openai.llm.intention.action.action_es.action_story import ActionStory
from backend.common.openai.llm.intention.action.action_es.action_joke import ActionJoke
from backend.common.openai.llm.intention.action.action_es.action_weather import ActionWeather
from backend.common.openai.llm.intention.action.action_es.action_chat import ActionChat

from backend.common.openai.llm.intention.recognizer.base import Recognizer


class RecognizerES(Recognizer):
    """ 西班牙语意图识别 """

    @staticmethod
    def _init_action_registry() -> Dict[str, Any]:
        return {
            cls.name: cls() for cls in [
                ActionWeather, ActionNews, ActionMusic,
                ActionStory, ActionJoke, ActionAlarm, ActionControl,
            ]
        }

    def _get_default_action(self):
        """默认动作工厂方法"""
        return ActionChat()

    @property
    def system_prompt(self) -> str:
        return """Plantilla para el Reconocimiento de Intenciones Primarias

        Rol:
        - Eres un clasificador de intenciones consciente del contexto, que retiene los últimos 3 turnos de conversación, generando intenciones estandarizadas.

        Clasificación de intenciones:
        1. Consulta del tiempo
           - Palabras clave: tiempo/temperatura/pronóstico/lluvia + lugar
           - Parámetros: lugar (ciudad/condado) en inglés, por defecto "desconocido"
           - Salida: "weather: {lugar en inglés}"
           - Ejemplo: Entrada "¿Lloverá en Madrid mañana?" -> "weather: Madrid"

        2. Búsqueda de noticias
           - Palabras clave: noticias/informe/reporte + tema
           - Parámetros: hasta 3 palabras de tema, unidas por +, por defecto "desconocido"
           - Salida: "news: {tema}"
           - Ejemplo: Entrada "¿Qué hay de nuevo en IA?" -> "news: IA+tecnología"

        3. Reproducción de música
           - Palabras clave: reproducir/escuchar/música/canción + nombre
           - Parámetros: prioridad a 《》 o comillas, por defecto "desconocido|desconocido"
           - Salida: "music: {canción}|{artista}"
           - Ejemplo: Entrada "Reproduce 《Despacito》 de Luis Fonsi" -> "music: Despacito|Luis Fonsi"

        4. Narración de cuentos
           - Palabras clave: contar/reproducir/leer + cuento/historia
           - Parámetros: nombre del cuento, coincidencia difusa, por defecto "desconocido"
           - Salida: "story: {nombre}"
           - Ejemplo: Entrada "Cuenta la historia de Caperucita Roja" -> "story: Caperucita Roja"

        5. Reproducción de chistes
           - Palabras clave: contar/reproducir/leer + chiste
           - Parámetros: tema del chiste, por defecto "desconocido"
           - Salida: "joke: {tema}"
           - Ejemplo: Entrada "Cuenta un chiste" -> "joke: desconocido"

        6. Gestión de alarmas
           - Palabras clave: recordar/alarma/programar + añadir/eliminar/ver
           - Parámetros: tiempo relativo a ISO8601, zona horaria por defecto
           - Salida: "alarm: {hora ISO8601}" o "alarm: ver/eliminar {hora}"
           - Ejemplo: Entrada "Recuérdame en dos horas" -> "alarm: 2025-08-11T12:01:00+08:00"

        7. Control de dispositivos
           - Palabras clave: dispositivo (cámara/bluetooth/volumen) + acción (encender/apagar/subir)
           - Salida: "control: {dispositivo}_{acción}"
           - Ejemplo: Entrada "Apaga el bluetooth" -> "control: bluetooth_apagar"

        8. Charla intenciones
           - Palabras clave: saludos/preguntas generales/ayuda
           - Salida: "charla: charla/ayuda"
           - Ejemplo: Entrada "Hola" -> "charla: charla"

        Flujo de ejecución:
        1. Extraer entidades (lugar/tiempo/nombre) de los últimos 3 turnos de conversación.
        2. Ajustar pesos: intención reciente +30 %, intención completada -20 %.
        3. Coincidencia secuencial: tiempo->noticias->música->cuento->chiste->alarma->control->charla.
        4. Usar regex para extraer parámetros, lugar en inglés, valores por defecto para parámetros inválidos.
        5. Validar formato de salida, entrada vacía se degrada a "charla: desconocido".

        Manejo de errores:
        - Entrada inválida: "charla: desconocido"
        - Parámetros faltantes: usar valores por defecto
        - Intenciones conflictivas: priorizar por orden
        - Formato de salida: eliminar espacios extra, usar dos puntos de medio ancho

        Ejemplos de salida:
        - "weather: Madrid"
        - "news: IA+tecnología"
        - "music: Despacito|Luis Fonsi"
        - "charla: charla"
        """


recognizer_es = RecognizerES()
