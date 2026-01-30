import argparse
from dotenv import load_dotenv
from agno.utils.pprint import pprint_run_response
from .coder.agent import get_agent as get_coder_agent
from .reviewer.agent import get_agent as get_reviewer_agent

# Загружаем переменные окружения из .env
load_dotenv()

def main():
    """
    Точка входа. Позволяет выбрать агента (Coder или Reviewer)
    и запускает его в стриминговом режиме.
    """
    parser = argparse.ArgumentParser(
        description="Kotic CLI - Локальный AI ассистент",
        epilog="Примеры использования: python -m kotic_cli --agent coder"
    )
    parser.add_argument(
        "--agent",
        type=str,
        choices=["coder", "reviewer"],
        required=True,
        help="Выберите агента для запуска: 'coder' или 'reviewer'."
    )
    args = parser.parse_args()

    print(f"🚀 Kotic CLI запущен...")
    print(f"Выбран агент: {args.agent}")
    print("-" * 20)

    if args.agent == "coder":
        agent = get_coder_agent()
        print("Coder Agent готов. Введите задачу:")
    elif args.agent == "reviewer":
        agent = get_reviewer_agent()
        print("Reviewer Agent готов. Введите текст для ревью:")
    else:
        raise ValueError("Неизвестный агент.")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("До свидания!")
                break

            if not user_input:
                continue

            print(f"Задача для агента {args.agent}: {user_input}")
            print("-" * 20)

            stream = agent.run(user_input, stream=True)
            pprint_run_response(stream, markdown=True)
            
            print("\n" + "-" * 20)

        except KeyboardInterrupt:
            print("\nДо свидания!")
            break

    print("🤖 Kotic CLI завершил свою работу.")

if __name__ == "__main__":
    main()