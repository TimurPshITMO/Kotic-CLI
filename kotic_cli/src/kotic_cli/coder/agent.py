import os
from agno.agent import Agent
from agno.models.openai.like import OpenAILike
from .tools import get_tools
from agno.db.sqlite import SqliteDb

SYSTEM_PROMPT = """Ты - Kotic CLI Coder, помощник программиста.

Твои возможности:
- Работа с файлами: читать, писать, список файлов
- Выполнение shell команд

Правила:
1. Читай файлы перед изменением
2. Объясняй что делаешь
3. Для изменения файла всегда используй инструмент `save_file`, передавая ему ПОЛНОЕ новое содержимое файла.
4. Тебе НЕ нужно разрешение для выполнения задач

Отвечай на русском языке.
"""

def get_agent():
    """
    Создает, настраивает и возвращает экземпляр agno.Agent.
    """
    api_key = os.getenv("YANDEX_API_KEY")
    base_url = os.getenv("YANDEX_API_BASE_URL")
    folder_id = os.getenv("YANDEX_FOLDER_ID")

    if not all([api_key, base_url]):
        raise ValueError("YANDEX_API_KEY или YANDEX_API_BASE_URL не установлены в .env файле.")

    yandex_model = OpenAILike(
        id=f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest",
        base_url=base_url,
        api_key=api_key,
    )

    agent = Agent(
        model=yandex_model,
        tools=get_tools(),
        instructions=SYSTEM_PROMPT,
        markdown=True,
        db=SqliteDb(db_file="coder_agent.db"),
    )
    return agent