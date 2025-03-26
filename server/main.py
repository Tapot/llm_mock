import logging
import os
import time
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi import Depends
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse


### processing parameters
# default tasks timeout (ms)
TASK_TIMEOUT_MS = 1000

### setup Redis parameters
# Redis endpoint URL
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
# Redis tasks queue name
REDIS_TASKS_QUEUE_NAME = os.getenv("REDIS_TASKS_QUEUE_NAME", "tasks_queue")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class MyFastApiApp(FastAPI):
    redis_client: redis.Redis
    index_html: str


@asynccontextmanager
async def lifespan(fastapi_app: MyFastApiApp) -> AsyncGenerator:
    with open("static/index.html", "r") as file:
        app.index_html = file.read()

    # create redis connections pool and check connection
    logger.info(
        f"Setup Redis connection at {REDIS_URL=} and queue {REDIS_TASKS_QUEUE_NAME=}"
    )
    fastapi_app.redis_client = redis.from_url(
        REDIS_URL, encoding="utf-8", decode_responses=True
    )
    await fastapi_app.redis_client.ping()
    yield
    #  close redis connections pool when the application is stopped.
    await fastapi_app.redis_client.close()


app = MyFastApiApp(lifespan=lifespan)


async def get_redis() -> redis.Redis:
    return app.redis_client


async def text_stream_generator(
    redis_client: redis.Redis, context: str
) -> AsyncGenerator:
    """A generator that send processing tasks, wait results and stream them back to the user."""
    logger.info(f"Run task for context {context=}")

    if context:
        start_time = time.time()
        task_id = str(uuid.uuid4())
        logger.info(f"Sending task {task_id=}")
        await redis_client.rpush(REDIS_TASKS_QUEUE_NAME, task_id + context)
        logger.debug(f"Wait results for task {task_id=}")

        while time.time() < start_time + TASK_TIMEOUT_MS:
            next_token = await redis_client.brpop([task_id], timeout=TASK_TIMEOUT_MS)
            logger.debug(f"Received token task {task_id=} {next_token=}")

            if next_token[1]:
                yield next_token[1]

            else:
                logger.info(f"Got termination for task {task_id=}")
                yield "Done!"
                break

        logger.info(f"Stop processing task {task_id=}")

    logger.info(f"Stop processing")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return app.index_html


@app.get("/generate")
async def generate(context: str, redis_client: redis.Redis = Depends(get_redis)):
    logger.info(f"Process GET request with context {context}")
    return EventSourceResponse(
        text_stream_generator(redis_client=redis_client, context=context)
    )
