#!/usr/bin/env python3

"""
Mock script - get N batched contexts via files, return tokens with random delay between them.
"""
import asyncio
import argparse
import random


# Default delay in seconds
MAX_DELAY_BETWEEN_WORDS = 2
# Maximum number of contexts to process at once
MAX_TASKS_BATCH_SIZE = 4


async def process_context(context_index: int, context: str):
    tokens = context.split()

    for i in range(len(tokens)):
        # Simulate delay between words
        delay = random.uniform(0, MAX_TASKS_BATCH_SIZE)
        # we have to flush print results each time because
        # otherwise it could be buffered and printed all at once
        print(f"{context_index}/{tokens[i % len(tokens)]}", flush=True)
        await asyncio.sleep(delay)

    print("")


async def main(contexts):
    contexts_data = []

    for i in contexts:
        with open(i, 'r') as f:
            contexts_data.append(f.read())

    if contexts_data:
        await asyncio.gather(
            *(
                process_context(context_index=context_index, context=context)
                for context_index, context in enumerate(contexts_data)
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process contexts with delays between words."
    )
    parser.add_argument(
        "contexts", nargs="+", help="Paths to the files containing contexts."
    )
    args = parser.parse_args()

    if len(args.contexts) > MAX_TASKS_BATCH_SIZE:
        exit(f"Too many contexts. Max batch size is {MAX_TASKS_BATCH_SIZE}.")

    asyncio.run(main(args.contexts))
