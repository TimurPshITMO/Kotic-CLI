import argparse
from dotenv import load_dotenv
from agno.utils.pprint import pprint_run_response
from .agent import get_agent

# Загружаем переменные окружения из .env
load_dotenv()

def main():
    """
    Точка входа. Принимает промпт и запускает агент в стриминговом режиме.
    """
    parser = argparse.ArgumentParser(description="Kotic CLI - Локальный AI ассистент")
    parser.add_argument("prompt", type=str, help="Ваша задача для AI агента.")
    args = parser.parse_args()

    print(f"🚀 Kotic CLI запущен...")
    print(f"Задача: {args.prompt}")
    print("-" * 20)

    # Получаем нашего преднастроенного агента
    agent = get_agent()

    # Запускаем агент в режиме потоковой передачи (stream=True).
    # Этот режим включает автономный цикл "мысль-действие".
    # Утилита pprint_run_response красиво печатает все события из потока.
    stream = agent.run(args.prompt, stream=True)
    pprint_run_response(stream, markdown=True)
    
    print("\n" + "-" * 20)
    print("🤖 Kotic CLI завершил свою работу.")

if __name__ == "__main__":
    main()