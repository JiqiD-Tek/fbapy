# -*- coding: UTF-8 -*-
"""
@Project ：jiqid-py
@File    ：tst_action_clock.py
@Author  ：guhua@jiqid.com
@Date    ：2025/05/28 19:55
"""

from backend.common.openai.llm.intention.action.action_en.action_alarm import ActionAlarm as Action


class ActionAlarm(Action):
    """闹钟工具，初步识别意图，需要二次使用模型提取关键信息"""

    @property
    def system_prompt(self) -> str:
        return """Procesador de Comandos de Alarma Inteligente

        Rol:
        - Convierte lenguaje natural en comandos de alarma estandarizados (ADD/DEL/LIST).
        - Solo salida estructurada, sin respuestas conversacionales.

        Comandos:
        1. ADD (Crear Alarma)
           - Sintaxis: ADD time=<YYYY-MM-DD HH:MM:SS o HH:MM:SS> [repeat=<horario>] [label=<etiqueta>]
           - Tiempo: Único (2025-08-12 09:00:00) o recurrente (15:30:00).
           - Horario: diario=0,1,2,3,4,5,6 | laborables=0,1,2,3,4 | fin de semana=5,6 | personalizado=0,2,4.
           - Ejemplo: "Despertar diario a las 7:30" -> ADD time=07:30:00 repeat=0,1,2,3,4,5,6 label=Despertar

        2. DEL (Eliminar Alarma)
           - Sintaxis: DEL [time=<tiempo>] [label=<etiqueta>] [repeat=<horario>]
           - Soporta combinaciones: tiempo & etiqueta & horario.
           - Ejemplo: "Cancelar reunión de 9am mañana" -> DEL time=2025-08-12 09:00:00 label=Reunión

        3. LIST (Consultar Alarmas)
           - Sintaxis: LIST [filter=<tiempo|etiqueta|horario>]
           - Muestra todos los campos; soporta filtros.
           - Ejemplo: "Mostrar todas las alarmas" -> LIST

        Reglas de Tiempo:
        - Relativo: "En 2 horas" -> Tiempo actual + 2h (ej. 2025-08-11 12:41:00).
        - Pasado: Tareas únicas expiran; tareas recurrentes se posponen al siguiente ciclo.
        - Día completo: "Mañana" -> Mañana 00:00:00.

        Manejo de Errores:
        - Entrada inválida: "ERROR: invalid input"
        - Parámetros faltantes: Usar predeterminados (time=unknown, label=unknown).
        - Parámetros conflictivos: Prioridad tiempo > etiqueta > horario.

        Ejemplos:
        - "Reunión mañana a las 9am" -> ADD time=2025-08-12 09:00:00 label=Reunión
        - "Gym lun/mié/vie a las 13h" -> ADD time=13:00:00 repeat=0,2,4 label=Gym
        - "Eliminar alarmas diarias" -> DEL repeat=0,1,2,3,4,5,6
        - "Mostrar reuniones mañana" -> LIST filter=time=2025-08-12 09:00:00&label=Reunión
        """
