from pathlib import Path
from typing import Literal, Optional, List, Dict, Any
from git import Repo, InvalidGitRepositoryError, GitCommandError
from github import Github, UnknownObjectException # Добавляем UnknownObjectException для удобства, хотя retry логика вне этого файла
from agno.tools import Toolkit # Импортируем Toolkit

class GitTools(Toolkit):
    """
    Инструменты для взаимодействия с Git репозиториями и GitHub API,
    с учетом ролей "coder" и "reviewer".
    """
    def __init__(self, base_dir: Path, github_token: Optional[str] = None, 
                 repo_owner: Optional[str] = None, repo_name: Optional[str] = None,
                 base_branch: str = "main", role: Literal['coder', 'reviewer'] = 'coder',
                 **kwargs):
        
        self.base_dir = base_dir
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_branch = base_branch
        self.role = role

        tools_for_role = []

        # Инструменты, доступные обеим ролям
        tools_for_role.extend([
            self.get_branches,
        ])

        if self.role == 'coder':
            tools_for_role.extend([
                self.create_feature_branch,
                self.commit_changes_on_feature_branch,
                self.create_pull_request,
                self.add_pr_labels
            ])
        elif self.role == 'reviewer':
            tools_for_role.extend([
                self.checkout_branch,
                self.get_diff,
                self.get_commit_details,
                self.get_file_content_from_branch,
                self.get_pull_request_details,
                self.get_pull_request_files,
                self.add_pull_request_comment,
                self.add_pr_labels
            ])
        else:
            raise ValueError(f"Неизвестная роль: {role}. Допустимые роли: 'coder', 'reviewer'.")

        super().__init__(name=f"git_tools", tools=tools_for_role, **kwargs)

    def _get_repo(self) -> Repo:
        try:
            repo = Repo(self.base_dir)
            return repo
        except InvalidGitRepositoryError:
            raise ValueError(f"'{self.base_dir}' не является действительным Git репозиторием.")

    def _get_github_repo(self):
        if not self.github_token:
            raise ValueError("GitHub токен не предоставлен.")
        if not self.repo_owner or not self.repo_name:
            raise ValueError("Владелец или имя репозитория не предоставлены при инициализации GitTools.")
        g = Github(self.github_token)
        return g.get_user(self.repo_owner).get_repo(self.repo_name)

    # --- Инструменты для Coder и Reviewer ---
    def get_branches(self) -> List[str]:
        """Возвращает список всех веток в репозитории."""
        repo = self._get_repo()
        return [branch.name for branch in repo.branches]

    # --- Инструменты ТОЛЬКО для Coder ---
    def create_feature_branch(self, new_branch_name: str, base_branch: Optional[str] = None) -> str:
        """
        Создает новую функциональную ветку от указанной базовой ветки (или основной, если не указана)
        и переключается на нее.
        """

        repo = self._get_repo()
        actual_base_branch = base_branch if base_branch else self.base_branch
        try:
            repo.git.checkout(actual_base_branch)
            new_branch = repo.create_head(new_branch_name)
            new_branch.checkout()
            return f"Функциональная ветка '{new_branch_name}' успешно создана и выбрана из '{actual_base_branch}'."
        except GitCommandError as e:
            raise ValueError(f"Ошибка при создании или переключении на ветку: {e}")

    def commit_changes_on_feature_branch(self, message: str) -> str:
        """
        Добавляет все изменения в staged-область, создает коммит с сообщением
        и пушит изменения в текущую ветку.
        """
        repo = self._get_repo()
        try:
            repo.git.add(A=True)

            if not repo.index.diff(None) and not repo.untracked_files:
                return "Нет изменений для коммита."
            
            repo.index.commit(message)
            current_branch = repo.active_branch.name
            
            repo.git.push('origin', current_branch) # Оригинальный код
            
            return f"Изменения успешно закоммичены и отправлены в ветку '{current_branch}' с сообщением: '{message}'."
        except GitCommandError as e:
            raise ValueError(f"Ошибка при коммите или пуше изменений: {e}")

    def create_pull_request(self, title: str, body: str) -> str:
        """
        Создает новый Pull Request на GitHub из текущей активной ветки в базовую ветку репозитория.
        """

        if not self.github_token:
            raise ValueError("GitHub токен не предоставлен для создания Pull Request.")
        if not self.repo_owner or not self.repo_name:
            raise ValueError("Владелец или имя репозитория не предоставлены при инициализации GitTools.")
        
        g = Github(self.github_token)
        try:
            repo_object = g.get_user(self.repo_owner).get_repo(self.repo_name)
            head_branch = self._get_repo().active_branch.name
            pr = repo_object.create_pull(title=title, body="# [Kotic Coder]\n"+body, head=head_branch, base=self.base_branch)
            return f"Pull Request успешно создан: {pr.html_url}"
        except Exception as e:
            raise ValueError(f"Ошибка при создании Pull Request: {e}")

    # --- Инструменты ТОЛЬКО для Reviewer ---
    def checkout_branch(self, branch_name: str) -> str:
        """
        Переключается на указанную ветку в локальном репозитории.
        """
        repo = self._get_repo()
        try:
            repo.git.checkout(branch_name)
            return f"Успешно переключено на ветку '{branch_name}'."
        except GitCommandError as e:
            raise ValueError(f"Ошибка при переключении на ветку '{branch_name}': {e}")

    def get_diff(self, head_branch: str, base_branch: str) -> str:
        """
        Возвращает текстовое представление различий (diff) между двумя ветками.
        """
        repo = self._get_repo()
        try:
            diff_text = repo.git.diff(base_branch, head_branch)
            if not diff_text:
                return f"Нет различий между ветками '{base_branch}' и '{head_branch}'."
            return diff_text
        except GitCommandError as e:
            raise ValueError(f"Ошибка при получении diff между '{base_branch}' и '{head_branch}': {e}")

    def get_commit_details(self, commit_sha: str) -> Dict[str, Any]:
        """
        Возвращает детали конкретного коммита по его SHA.
        """
        repo = self._get_repo()
        try:
            commit = repo.commit(commit_sha)
            details = {
                "sha": commit.hexsha,
                "author": commit.author.name,
                "author_email": commit.author.email,
                "committed_date": commit.committed_datetime.isoformat(),
                "message": commit.message.strip(),
                "files_changed": [item.a_path for item in commit.stats.files.keys()] # Changed from commit.stats.files to keys()
            }
            return details
        except Exception as e:
            raise ValueError(f"Ошибка при получении деталей коммита '{commit_sha}': {e}")

    def get_pull_request_details(self, pr_number: int) -> Dict[str, Any]:
        """
        Возвращает подробную информацию о конкретном Pull Request.
        """
        repo_object = self._get_github_repo()
        try:
            pr = repo_object.get_pull(pr_number)
            details = {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "user": pr.user.login,
                "html_url": pr.html_url,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "mergeable": pr.mergeable,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
            }
            return details
        except Exception as e:
            raise ValueError(f"Ошибка при получении деталей Pull Request #{pr_number}: {e}")

    def get_pull_request_files(self, pr_number: int) -> List[Dict[str, Any]]:
        """
        Возвращает список файлов, измененных в Pull Request.
        """
        repo_object = self._get_github_repo()
        try:
            pr = repo_object.get_pull(pr_number)
            files = pr.get_files()
            file_list = []
            for file in files:
                file_list.append({
                    "filename": file.filename,
                    "status": file.status, # added, modified, removed
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "raw_url": file.raw_url,
                })
            return file_list
        except Exception as e:
            raise ValueError(f"Ошибка при получении файлов Pull Request #{pr_number}: {e}")

    def add_pull_request_comment(self, pr_number: int, comment_body: str, commit_id: Optional[str] = None, path: Optional[str] = None, position: Optional[int] = None) -> str:
        """
        Добавляет комментарий к Pull Request.
        Если commit_id, path и position указаны, комментарий добавляется как review comment к конкретной строке.
        В противном случае добавляется общий комментарий к PR.
        """
        repo_object = self._get_github_repo()
        try:
            pr = repo_object.get_pull(pr_number)
            if commit_id and path and position is not None:
                comment = pr.create_review_comment(body="# [Kotic Reviewer]\n"+comment_body, commit_id=commit_id, path=path, position=position)
            else:
                comment = pr.create_issue_comment("# [Kotic Reviewer]\n"+comment_body)
            return f"Комментарий к Pull Request успешно добавлен: {comment.html_url}"
        except Exception as e:
            raise ValueError(f"Ошибка при добавлении комментария к Pull Request #{pr_number}: {e}")

    def get_file_content_from_branch(self, file_path: str, branch_name: str) -> str:
        """
        Возвращает содержимое файла из указанной ветки.
        """
        repo = self._get_repo()
        try:
            content = repo.git.show(f"{branch_name}:{file_path}")
            return content
        except GitCommandError as e:
            raise ValueError(f"Ошибка Git при чтении файла '{file_path}' из ветки '{branch_name}': {e}")
        except Exception as e:
            raise ValueError(f"Ошибка при чтении файла '{file_path}' из ветки '{branch_name}': {e}")

            
    def add_pr_labels(self, pr_number: int, labels: List[str]) -> str:
        """
        Добавляет метки к Pull Request.
        """
        repo_object = self._get_github_repo()
        try:
            pr = repo_object.get_pull(pr_number)
            pr.add_to_labels(*labels)
            return f"Метки '{', '.join(labels)}' успешно добавлены к Pull Request #{pr_number}."
        except Exception as e:
            raise ValueError(f"Ошибка при добавлении меток к Pull Request #{pr_number}: {e}")