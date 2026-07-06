import logging

from api.core.procrastinate_app import app
from api.core.settings import PROCRASTINATE_QUEUE

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main() -> None:
    app.open()
    try:
        app.run_worker(queues=[PROCRASTINATE_QUEUE])
    finally:
        app.close()


if __name__ == "__main__":
    main()
