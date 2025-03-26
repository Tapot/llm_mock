import asyncio
import logging
import os
import time
import tempfile
import dataclasses
import sys
from contextlib import asynccontextmanager
import redis.asyncio as redis


### setup Redis parameters
# Redis endpoint URL
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
# Redis tasks queue name
REDIS_TASKS_QUEUE_NAME = os.getenv("REDIS_TASKS_QUEUE_NAME", "tasks_queue")

### batching parameters
MAX_TASKS_BATCH_SIZE = int(os.getenv("MAX_TASKS_BATCH_SIZE", 4))
WAIT_BATCH_MS = float(os.getenv("WAIT_BATCH_MS", 250))

### logging configuration
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

### get the mock lLM script path
script_path: str = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "scripts", "llm_mock.py"
)


@dataclasses.dataclass
class Task:
    task_id: str
    context: str


@asynccontextmanager
async def redis_connection():
    pool = redis.ConnectionPool.from_url(
        REDIS_URL, encoding="utf-8", decode_responses=True
    )
    client = redis.Redis(connection_pool=pool)
    try:
        await client.ping()
        yield client
    finally:
        await pool.disconnect()


async def get_task_from_redis(
    redis_client: redis.Redis, timeout_sec: int
) -> Task | None:
    redis_item = await redis_client.blpop([REDIS_TASKS_QUEUE_NAME], timeout=timeout_sec)

    if redis_item:
        task_data = redis_item[1]

        result = Task(task_id=task_data[:36], context=task_data[36:])
        logger.info(f"Got task {result.task_id}")
        return result

    else:
        return None


async def send_tokens_to_redis(
    redis_client: redis.Redis, stdout_line: str, tasks: list[Task]
) -> None:
    split_result = stdout_line.split("/", 1)

    if len(split_result) == 2:
        task_index = int(split_result[0])
        token = split_result[1]
        task_id = tasks[task_index].task_id
        logger.debug(f"Send token for {task_id=} {token=}")
        await redis_client.rpush(task_id, token)

    else:
        # process the error here, the proper way depends on the concrete use-case
        logger.error(f"Invalid line format from the LLM process output: {stdout_line}")


async def main():
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Redis tasks queue name: {REDIS_TASKS_QUEUE_NAME}")

    async with redis_connection() as redis_client:
        logger.info("Starting the main loop")

        while True:
            tasks: list[Task] = []
            logger.info("Wait the first task from Redis")
            first_task: Task = await get_task_from_redis(redis_client, timeout_sec=0)

            if not first_task:
                logger.debug("The first task was not received")
                await asyncio.sleep(0)
                continue

            else:
                tasks.append(first_task)

            current_time = time.time()
            logger.info(f"Wait additional tasks {current_time=}")
            additional_task_timeout: float = WAIT_BATCH_MS

            while len(tasks) < MAX_TASKS_BATCH_SIZE and additional_task_timeout:
                additional_task_timeout = max(
                    0.0, WAIT_BATCH_MS - (time.time() - current_time) * 1000
                )

                if additional_task_timeout:
                    logger.debug(
                        f"Wait an additional task from Redis with timeout {additional_task_timeout} ms"
                    )

                    # timeout_sec specified as int - in sec, but redis supports float for ms
                    # noinspection PyTypeChecker
                    task = await get_task_from_redis(
                        redis_client, timeout_sec=additional_task_timeout / 1000
                    )

                    if task:
                        tasks.append(task)

            logger.info(f"Got {len(tasks)} tasks for batch request")

            cmd = [script_path]

            for task in tasks:
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                    temp_file.write(task.context)
                    cmd.append(temp_file.name)

            logger.debug(f"Configs were saved in files.")
            logger.debug(f"Run {cmd=}")

            llm_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
            )
            # set any value for starting the while loop
            stdout: bytes = b"1"

            while stdout:
                stdout = await llm_process.stdout.readline()

                if stdout and stdout != b"\n":
                    logger.debug(f"Got stdout from LLM process {stdout=}")
                    await send_tokens_to_redis(
                        redis_client=redis_client,
                        stdout_line=stdout.decode().rstrip(),
                        tasks=tasks,
                    )

            for task in tasks:
                await redis_client.rpush(task.task_id, "")

            await llm_process.wait()


if __name__ == "__main__":
    asyncio.run(main())
