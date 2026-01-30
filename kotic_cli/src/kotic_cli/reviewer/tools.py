from pathlib import Path
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

def get_tools():
    """
    Возвращает список инициализированных и "песочница" наборов инструментов
    agno для Reviewer-агента.
    """
    # Определяем корневую директорию проекта. Все действия будут ограничены ей.
    # На текущем этапе для ревьюера также используется директория 'tests'.
    # В дальнейшем это будет изменено для доступа ко всему репозиторию.
    sandbox_path = Path.cwd() / "tests" 

    print(f" Reviewer Sandbox: Инструменты ограничены директорией: {sandbox_path}")

    return [
        FileTools(base_dir=sandbox_path),
        ShellTools(base_dir=sandbox_path)
    ]
