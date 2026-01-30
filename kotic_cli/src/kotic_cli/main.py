import argparse
from dotenv import load_dotenv
from agno.utils.pprint import pprint_run_response
from .coder.agent import get_agent as get_coder_agent
from .reviewer.agent import get_agent as get_reviewer_agent
from .utils.logger_config import logger # Import the configured logger

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

    logger.info(f"🚀 Kotic CLI запущен...")
    logger.info(f"Выбран агент: {args.agent}")
    logger.info("-" * 20)

    if args.agent == "coder":
        agent = get_coder_agent()
        logger.info("Coder Agent готов. Введите задачу:")
    elif args.agent == "reviewer":
        agent = get_reviewer_agent()
        logger.info("Reviewer Agent готов. Введите текст для ревью:")
    else:
        # This case is technically caught by argparse choices, but good for defensive programming
        logger.error(f"Неизвестный агент: {args.agent}. Выберите 'coder' или 'reviewer'.")
        raise ValueError("Неизвестный агент.")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                logger.info("До свидания!")
                break

            if not user_input:
                continue

            logger.info(f"Задача для агента {args.agent}: {user_input}")
            logger.info("-" * 20)

            stream = agent.run(user_input, stream=True)
            pprint_run_response(stream, markdown=True)
            
            logger.info("\n" + "-" * 20)

        except KeyboardInterrupt:
            logger.info("\nДо свидания!")
            break
        except Exception as e:
            logger.exception(f"Произошла ошибка при выполнении агента: {e}")

    logger.info("🤖 Kotic CLI завершил свою работу.")

if __name__ == "__main__":
    main()