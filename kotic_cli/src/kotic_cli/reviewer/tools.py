from pathlib import Path
from agno.tools.file import FileTools
# ShellTools не используется для reviewer, так как ему не разрешено изменять систему
from ..utils.git_tools import GitTools # Импортируем наш GitTools Toolkit
from ..utils.logger_config import logger # Import the configured logger

def get_tools(base_dir: Path, github_token: str, repo_owner: str, repo_name: str, base_branch: str = "main", pr_number: int = None):
    """
    Возвращает список инициализированных и "песочница" наборов инструментов
    agno для Reviewer-агента.
    """
    if pr_number is None:
        logger.error("Для Reviewer Agent необходимо указать pr_number.")
        raise ValueError("Для Reviewer Agent необходимо указать pr_number.")

    logger.info(f" Reviewer Sandbox: Инструменты ограничены директорией: {base_dir}")

    # Создаем экземпляр GitTools для Reviewer
    git_tools_instance = GitTools(
        base_dir=base_dir, 
        github_token=github_token, 
        repo_owner=repo_owner, 
        repo_name=repo_name,
        base_branch=base_branch,
        role='reviewer' # Явно указываем роль 'reviewer'
    )

    # FileTools для Reviewer: только чтение
    file_tools_instance = FileTools(
        base_dir=base_dir,
        enable_save_file=False,
        enable_delete_file=False,
        # Убедитесь, что нет опций, позволяющих модифицировать файлы
        # enable_write_file=False (если FileTools имеет такую опцию)
    )

    return [
        file_tools_instance,
        git_tools_instance # Добавляем сам экземпляр GitTools Toolkit
    ]