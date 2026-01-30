from pathlib import Path
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools
from ..utils.git_tools import GitTools # Импортируем наш GitTools Toolkit
from ..utils.logger_config import logger # Import the configured logger

def get_tools(base_dir: Path, github_token: str, repo_owner: str, repo_name: str, base_branch: str = "main"):
    """
    Возвращает список инициализированных наборов инструментов
    """
    logger.info(f" Sandbox: Инструменты ограничены директорией: {base_dir}")

    # Создаем экземпляр GitTools (который теперь является Toolkit)
    git_tools_instance = GitTools(
        base_dir=base_dir, 
        github_token=github_token, 
        repo_owner=repo_owner, 
        repo_name=repo_name,
        base_branch=base_branch,
        role='coder' # Явно указываем роль 'coder'
    )

    return [
        FileTools(base_dir=base_dir),
        ShellTools(base_dir=base_dir),
        git_tools_instance # Добавляем сам экземпляр Toolkit
    ]