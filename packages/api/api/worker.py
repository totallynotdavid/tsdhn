import logging
import os

from redis import Redis
from rq import Queue, Worker

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main() -> None:
    redis = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    queue = Queue("tsdhn_queue", connection=redis)
    worker = Worker([queue], connection=redis)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
