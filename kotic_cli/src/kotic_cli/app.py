import os
import hmac
import hashlib
import json
import jwt
from datetime import datetime, timedelta, timezone
import httpx # Для HTTP-запросов к GitHub API

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends
from starlette.status import HTTP_200_OK

# Загружаем переменные окружения
load_dotenv()

app = FastAPI(title="Kotic CLI GitHub Webhook Listener")

# --- Конфигурация GitHub App из переменных окружения ---
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH") # Путь к .pem файлу
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# Проверка наличия критически важных переменных окружения
if not GITHUB_APP_ID:
    raise ValueError("GITHUB_APP_ID не установлен в .env")
if not GITHUB_PRIVATE_KEY_PATH:
    raise ValueError("GITHUB_PRIVATE_KEY_PATH не установлен в .env (укажите путь к .pem файлу)")
if not GITHUB_WEBHOOK_SECRET:
    raise ValueError("GITHUB_WEBHOOK_SECRET не установлен в .env")

# Чтение приватного ключа
try:
    with open(GITHUB_PRIVATE_KEY_PATH, 'rb') as f:
        PRIVATE_KEY = f.read()
except FileNotFoundError:
    raise FileNotFoundError(f"Приватный ключ не найден по пути: {GITHUB_PRIVATE_KEY_PATH}")
except Exception as e:
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

# --- Функции для вызова агентов (заглушки) ---

async def trigger_code_agent(event_type: str, payload: dict, installation_id: int):
    """
    Заглушка для запуска Code Agent.
    Здесь должна быть реализована логика:
    1. Получение installation_access_token
    2. Извлечение необходимых данных из payload (например, Issue title, body, repo details)
    3. Вызов реальной логики Code Agent (возможно, в отдельном процессе или асинхронно)
    """
    print(f"--- Trigger Code Agent for event: {event_type} ---")
    print(f"Payload ID: {payload.get('issue', {}).get('id') or payload.get('pull_request', {}).get('id')}")
    print(f"Installation ID: {installation_id}")
    # Пример получения токена установки:
    # token = await get_installation_access_token(installation_id)
    # print(f"Obtained installation token (first 10 chars): {token[:10]}...")
    # Здесь можно вызвать вашу логику Code Agent, передав ему токен и данные
    print("Code Agent logic would be executed here.")

async def trigger_reviewer_agent(event_type: str, payload: dict, installation_id: int):
    """
    Заглушка для запуска Reviewer Agent.
    Здесь должна быть реализована логика:
    1. Получение installation_access_token
    2. Извлечение необходимых данных из payload (например, PR number, repo details, SHA)
    3. Вызов реальной логики Reviewer Agent (возможно, в отдельном процессе или асинхронно)
    """
    print(f"--- Trigger Reviewer Agent for event: {event_type} ---")
    print(f"Payload ID: {payload.get('pull_request', {}).get('id')}")
    print(f"Installation ID: {installation_id}")
    # Пример получения токена установки:
    # token = await get_installation_access_token(installation_id)
    # print(f"Obtained installation token (first 10 chars): {token[:10]}...")
    # Здесь можно вызвать вашу логику Reviewer Agent, передав ему токен и данные
    print("Reviewer Agent logic would be executed here.")

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
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header missing")

    body = await request.body()
    
    # Расчет ожидаемой подписи
    mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=403, detail="Invalid X-Hub-Signature-256")

    # 2. Обработка payload
    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event")
    installation_id = payload.get("installation", {}).get("id")

    if not installation_id:
        print(f"Warning: Webhook received without installation ID for event {event_type}. Skipping agent trigger.")
        return {"message": "Webhook received, but no installation ID."}

    print(f"Received GitHub event: {event_type} for installation {installation_id}")

    # 3. Диспетчеризация событий для агентов
    if event_type == "issues":
        action = payload.get("action")
        if action in ["opened", "edited", "labeled"]:
            await trigger_code_agent(event_type, payload, installation_id)
    elif event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize"]: # synchronize - когда новые коммиты пушатся в PR
            await trigger_reviewer_agent(event_type, payload, installation_id)
            # Также Code Agent может быть запущен для итераций, если Reviewer Agent оставляет негативные комментарии
            # Например, если Reviewer Agent оставляет комментарий и это событие вызывает webhook `issue_comment` или `pull_request_review_comment`
            # Можно здесь же добавить условие, чтобы Code Agent реагировал на такие события
            # if action == "edited" and payload.get("comment", {}).get("user", {}).get("type") == "Bot":
            #     await trigger_code_agent(event_type, payload, installation_id) # Пример
    elif event_type == "issue_comment":
        # Если это комментарий от Reviewer Agent, который требует изменений
        comment = payload.get("comment", {})
        if comment.get("user", {}).get("type") == "Bot" and "changes requested" in comment.get("body", "").lower():
            # Здесь можно добавить более сложную логику, чтобы определить, действительно ли это запрос на изменения от Reviewer
            await trigger_code_agent(event_type, payload, installation_id)
    elif event_type == "check_run":
        action = payload.get("action")
        if action == "completed":
            # Check Run завершился, возможно, нужно запустить Reviewer Agent для анализа
            await trigger_reviewer_agent(event_type, payload, installation_id)
    # Добавьте другие условия для обработки других событий GitHub App

    return {"message": f"Webhook for {event_type} processed."}

# Опциональный корневой эндпоинт для проверки работы сервера
@app.get("/")
async def root():
    return {"message": "Kotic CLI GitHub Webhook Listener is running."}
