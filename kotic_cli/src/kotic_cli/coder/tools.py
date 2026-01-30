from pathlib import Path
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

def get_tools():
    """
    Возвращает список инициализированных и "песочница" наборов инструментов
    agno, как это сделано в примере task2.
    """
    # Определяем корневую директорию проекта. Все действия будут ограничены ей.
    # Path.cwd() получает текущую рабочую директорию, где запущен скрипт.
    sandbox_path = Path.cwd() / "tests"

    print(f" Sandbox: Инструменты ограничены директорией: {sandbox_path}")

    return [
        FileTools(base_dir=sandbox_path),
        ShellTools(base_dir=sandbox_path)
    ]
