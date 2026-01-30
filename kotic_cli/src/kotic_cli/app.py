import os
import hmac
import hashlib
import json
import jwt
from datetime import datetime, timedelta, timezone
import httpx # Для HTTP-запросов к GitHub API
import asyncio # Импорт для асинхронных задач
import shutil # Для очистки временных директорий
import tempfile # Для создания временных директорий
from pathlib import Path # Для работы с путями
from git import Repo, GitCommandError # Для клонирования репозитория

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_200_OK

from .coder.agent import get_agent as get_code_agent
from .reviewer.agent import get_agent as get_reviewer_agent
from .utils.git_tools import GitTools # Для прямого доступа к методам GitTools при обертке в executor
from .utils.logger_config import logger # Import the configured logger
from github import UnknownObjectException # Для обработки исключений PyGithub

# Загружаем переменные окружения
load_dotenv()

app = FastAPI(title="Kotic CLI GitHub Webhook Listener")

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://github",
    "http://github.com"
    "https://github",
    "https://github.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Конфигурация GitHub App из переменных окружения ---
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH") # Путь к .pem файлу
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# Проверка наличия критически важных переменных окружения
if not GITHUB_APP_ID:
    logger.error("GITHUB_APP_ID не установлен в .env")
    raise ValueError("GITHUB_APP_ID не установлен в .env")
if not GITHUB_PRIVATE_KEY_PATH:
    logger.error("GITHUB_PRIVATE_KEY_PATH не установлен в .env (укажите путь к .pem файлу)")
    raise ValueError("GITHUB_PRIVATE_KEY_PATH не установлен в .env (укажите путь к .pem файлу)")
if not GITHUB_WEBHOOK_SECRET:
    logger.error("GITHUB_WEBHOOK_SECRET не установлен в .env")
    raise ValueError("GITHUB_WEBHOOK_SECRET не установлен в .env")

# Чтение приватного ключа
try:
    with open(GITHUB_PRIVATE_KEY_PATH, 'rb') as f:
        PRIVATE_KEY = f.read()
except FileNotFoundError:
    logger.exception(f"Приватный ключ не найден по пути: {GITHUB_PRIVATE_KEY_PATH}")
    raise FileNotFoundError(f"Приватный ключ не найден по пути: {GITHUB_PRIVATE_KEY_PATH}")
except Exception as e:
    logger.exception(f"Ошибка при чтении приватного ключа: {e}")
    raise Exception(f"Ошибка при чтении приватного ключа: {e}")

# --- Вспомогательные функции для аутентификации GitHub App ---

def generate_jwt() -> str:
    """Генерирует JSON Web Token для аутентификации GitHub App."""
    now = datetime.now(timezone.utc)
    payload = {
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()), # Токен действителен 10 минут
        "iss": GITHUB_APP_ID,
    }
    encoded_jwt = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
    return encoded_jwt

async def get_installation_access_token(installation_id: int) -> str:
    """
    Получает токен доступа установки для конкретной установки GitHub App.
    """
    jwt_token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    # Используем httpx для асинхронных запросов
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers=headers,
            timeout=30.0 # Устанавливаем таймаут
        )
        response.raise_for_status() # Вызовет исключение для статусов 4xx/5xx
        token_data = response.json()
        return token_data["token"]

# --- Функции для вызова агентов ---

async def clone_repository_async(authenticated_repo_clone_url: str, temp_repo_dir: Path):
    """Асинхронно клонирует репозиторий."""
    # This will run in a separate thread pool executor
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, # Use default executor
        Repo.clone_from,
        authenticated_repo_clone_url,
        temp_repo_dir
    )
    logger.info(f"Репозиторий успешно клонирован в '{temp_repo_dir}'")

async def execute_git_tools_method_with_retry(git_tools_instance: GitTools, method_name: str, *args, **kwargs):
    """
    Выполняет метод GitTools с асинхронными повторными попытками.
    Предполагается, что методы GitTools синхронны.
    """
    max_retries = 5
    retry_delay_seconds = 5
    loop = asyncio.get_running_loop()
    
    for attempt in range(max_retries):
        try:
            result = await loop.run_in_executor(
                None, # Use default executor
                getattr(git_tools_instance, method_name),
                *args,
                **kwargs
            )
            return result
        except UnknownObjectException: # Ловим специфическое исключение PyGithub для PR
            logger.warning(f"Ветка или PR не найдены на GitHub API. Повторная попытка через {retry_delay_seconds} секунд... (Попытка {attempt + 1}/{max_retries})")
            await asyncio.sleep(retry_delay_seconds)
        except GitCommandError as e: # Ловим ошибки GitPython
            logger.warning(f"Ошибка GitCommandError при выполнении {method_name}: {e}. Повторная попытка через {retry_delay_seconds} секунд... (Попытка {attempt + 1}/{max_retries})")
            await asyncio.sleep(retry_delay_seconds)
        except Exception as e:
            # Для других неожиданных ошибок можно сразу выбросить
            logger.exception(f"Неожиданная ошибка при выполнении {method_name}: {e}")
            raise

    logger.error(f"Не удалось выполнить '{method_name}' после {max_retries} попыток.")
    raise ValueError(f"Не удалось выполнить '{method_name}' после {max_retries} попыток.")


async def trigger_code_agent(event_type: str, payload: dict, installation_id: int):
    """
    Запускает Code Agent для обработки Issue.
    """
    logger.info(f"--- Trigger Code Agent for event: {event_type} ---")
    issue_id = payload.get('issue', {}).get('id')
    pr_id = payload.get('pull_request', {}).get('id') # Может быть PR, если это, например, check_run webhook
    logger.info(f"Payload ID: {issue_id or pr_id}")
    logger.info(f"Installation ID: {installation_id}")

    issue_title = payload.get("issue", {}).get("title")
    issue_body = payload.get("issue", {}).get("body")
    repo_owner = payload.get("repository", {}).get("owner", {}).get("login")
    repo_name = payload.get("repository", {}).get("name")
    repo_clone_url = payload.get("repository", {}).get("clone_url") # HTTPS clone URL
    base_branch = payload.get("repository", {}).get("default_branch", "main") # Основная ветка репозитория

    if not all([issue_title, repo_owner, repo_name, repo_clone_url]):
        logger.warning("Отсутствуют необходимые данные в payload для запуска Code Agent.")
        logger.debug(f"Missing data: issue_title={issue_title}, repo_owner={repo_owner}, repo_name={repo_name}, repo_clone_url={repo_clone_url}")
        return

    temp_repo_dir = None
    try:
        # 1. Создание временной папки
        temp_repo_dir = Path(tempfile.mkdtemp(prefix=f"kotic_coder_repo_{repo_name}_{issue_id or pr_id}_"))
        logger.info(f"Создана временная директория для репозитория: {temp_repo_dir}")

        # 2. Получаем installation token
        installation_token = await get_installation_access_token(installation_id)
        
        # 3. Клонирование репозитория с использованием токена для аутентификации
        authenticated_repo_clone_url = f"https://x-access-token:{installation_token}@{repo_clone_url.split('//')[1]}"
        await clone_repository_async(authenticated_repo_clone_url, temp_repo_dir)
        # log is already in clone_repository_async: logger.info(f"Репозиторий '{repo_name}' успешно клонирован в '{temp_repo_dir}'")

        # 4. Инициализация CodeAgent с инструментами
        code_agent = get_code_agent(
            base_dir=temp_repo_dir, 
            github_token=installation_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
            base_branch=base_branch
        )
        logger.info("Code Agent initialized. Running with Issue...")

        # 5. Передача Issue агенту
        agent_prompt = f"Исправь возникший issue: {issue_title}\n\nОписание: {issue_body}\n\nРепозиторий находится по пути: {temp_repo_dir}. Владелец репозитория: {repo_owner}, Имя репозитория: {repo_name}. Основная ветка: {base_branch}. Тебе нужно создать новую функциональную ветку, внести изменения, закоммитить их и создать Pull Request."
        
        response = await code_agent.arun(agent_prompt)

        logger.info(f"--- Code Agent Response for {issue_id or pr_id} ---")
        logger.info(response.content)

    except ValueError as e:
        logger.error(f"Error initializing or running Code Agent: {e}")
    except Exception as e:
        logger.exception(f"Error during Code Agent execution: {e}")

async def trigger_reviewer_agent(event_type: str, payload: dict, installation_id: int):
    """
    Запускает Reviewer Agent.
    """
    logger.info(f"--- Trigger Reviewer Agent for event: {event_type} ---")
    pr_number = payload.get('pull_request', {}).get('number')
    repo_owner = payload.get("repository", {}).get("owner", {}).get("login")
    repo_name = payload.get("repository", {}).get("name")
    repo_clone_url = payload.get("repository", {}).get("clone_url") # HTTPS clone URL
    base_branch = payload.get("repository", {}).get("default_branch", "main") # Основная ветка репозитория
    pr_title = payload.get("pull_request", {}).get("title")
    pr_body = payload.get("pull_request", {}).get("body")

    if not all([pr_number, repo_owner, repo_name, repo_clone_url]):
        logger.warning("Отсутствуют необходимые данные в payload для запуска Reviewer Agent.")
        logger.debug(f"Missing data: pr_number={pr_number}, repo_owner={repo_owner}, repo_name={repo_name}, repo_clone_url={repo_clone_url}")
        return

    temp_repo_dir = None
    try:
        # 1. Создание временной папки
        temp_repo_dir = Path(tempfile.mkdtemp(prefix=f"kotic_reviewer_repo_{repo_name}_{pr_number}_"))
        logger.info(f"Создана временная директория для репозитория: {temp_repo_dir}")

        # 2. Получаем installation token
        installation_token = await get_installation_access_token(installation_id)
        
        # 3. Клонирование репозитория с использованием токена для аутентификации
        authenticated_repo_clone_url = f"https://x-access-token:{installation_token}@{repo_clone_url.split('//')[1]}"
        await clone_repository_async(authenticated_repo_clone_url, temp_repo_dir)
        # log is already in clone_repository_async: logger.info(f"Репозиторий '{repo_name}' успешно клонирован в '{temp_repo_dir}'")

        # 4. Инициализация ReviewerAgent с инструментами
        reviewer_agent = get_reviewer_agent(
            base_dir=temp_repo_dir, 
            github_token=installation_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
            base_branch=base_branch,
            pr_number=pr_number
        )
        logger.info("Reviewer Agent initialized. Running with PR details...")

        # 5. Передача деталей PR агенту
        agent_prompt = f"Выполни ревью Pull Request #{pr_number}: {pr_title}\n\nОписание: {pr_body}\n\nРепозиторий находится по пути: {temp_repo_dir}. Владелец репозитория: {repo_owner}, Имя репозитория: {repo_name}. Основная ветка: {base_branch}."
        
        response = await reviewer_agent.arun(agent_prompt)

        logger.info(f"--- Reviewer Agent Response for PR #{pr_number} ---")
        logger.info(response.content)

    except ValueError as e:
        logger.error(f"Error initializing or running Reviewer Agent: {e}")
    except Exception as e:
        logger.exception(f"Error during Reviewer Agent execution: {e}")

# --- Обработчик вебхуков GitHub ---

@app.post("/webhook")
async def github_webhook(request: Request):
    """
    Основной эндпоинт для приема вебхуков от GitHub.
    Проверяет подпись, определяет тип события и запускает соответствующего агента.
    """
    # 1. Проверка секрета вебхука (сигнатуры)
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning("X-Hub-Signature-256 header missing in webhook request. Returning 401.")
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header missing")

    body = await request.body()
    
    # Расчет ожидаемой подписи
    mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        logger.error("Invalid X-Hub-Signature-256 in webhook request. Returning 403.")
        raise HTTPException(status_code=403, detail="Invalid X-Hub-Signature-256")

    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event")
    installation_id = payload.get("installation", {}).get("id")

    if not installation_id:
        logger.warning(f"Webhook received without installation ID for event {event_type}. Skipping agent trigger.")
        return {"message": "Webhook received, but no installation ID."}

    logger.info(f"Received GitHub event: {event_type} for installation {installation_id}")
    logger.debug(f"Event Type: {event_type}")
    # 3. Диспетчеризация событий для агентов
    if event_type == "issues":
        action = payload.get("action")
        if action in ["opened", "edited", "labeled"]:
            asyncio.create_task(trigger_code_agent(event_type, payload, installation_id))
    elif event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize"]:
            asyncio.create_task(trigger_reviewer_agent(event_type, payload, installation_id))
    elif event_type == "issue_comment":
        comment = payload.get("comment", {})
        if comment.get("user", {}).get("type") == "Bot" and "changes requested" in comment.get("body", "").lower():
            asyncio.create_task(trigger_code_agent(event_type, payload, installation_id))
    elif event_type == "check_run":
        action = payload.get("action")
        if action == "completed":
            asyncio.create_task(trigger_reviewer_agent(event_type, payload, installation_id))

    return {"message": f"Webhook for {event_type} processed. Agent tasks started in background."}

# Опциональный корневой эндпоинт для проверки работы сервера
@app.get("/")
async def root():
    return {"message": "Kotic CLI GitHub Webhook Listener is running."}