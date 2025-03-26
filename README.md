# API with LLM mocked slow worker
Test service for calling a mock llm script

# How to use it
- Ensure you have Docker and Docker Compose are installed. You can check this by running:

`docker --version`

`docker-compose --version`
- Run all modules with

`docker-compose up --build`

# Components
## LLM Mock script

## API Server
FastAPI server with simple test page and `GET /generate` handler with SSE streaming

Processing logic for the `/generate` endpoint:
- get a request with a context
- set task ID - UUID should be good enough here
- put the task into Redis
- wait results from worker in resid with the task ID
- listen for SSE events from worker until we receive result

## Worker
Just a simple async python script with logic:
- get a task from Redis
- wait other tasks in some time window
- if we get 4 tasks - run the slow script
- if we waited enough time - run with current amount of tasks
- return results with redis as fast as possible - when we got it from stdout
- send contexts to the slow script with files - to prevent es escaping symbols. 
We can use base64 here or another ways to send the data

# Implementation Timeline and reasoning
## Timeline
2 hours on Saturday
- make implementation plan
- refresh how Redis works
- take a look what to do with SSE streaming in FastAPI

4 hours on Monday
- implement the API server
- implement the worker
- test everything together

2 hours on Wednesday
- create github repo
- push code to github
- test it all together again
- write the readme file

All code I wrote myself, except html test page - LLM did it fast and it looks nice for me.

## Reasoning
- For API I decided to use FastAPI - it supports SSE streaming and I worked with it last years
- For communication with worker I decided to use Redis as it is simple and easy to use and has all minimum things to send tasks to worker
- For mocking LLM I decided to use a simple python script that will sleep for some random time and returns the same string
If we want to test something more complicate, we can use pre-defined texts or instruction for the script behaviour

For example: start the initial text with delay parameters for the mock script. 
- And for worker I used a simple python script too. 
If we want to implement something more complicate with HTTP handlers for monitoring or healthchecks, we can make it with FastAPI too

# Testing, Monitoring thoughts
## Testing
- For testing I think we could use pytest for services testing
- We can also add tests for the worker and LLM mock script separately with mocking delays
- For the server we can mock Redis calls and mostly test API endpoints


## Monitoring
For the monitoring I think we should: 
- measure time for overall requests, make quantiles charts, top-slow requests
- also we can add healthcheck endpoint for the server and worker and handlers with some stats
- CPU/memory/disk usage monitoring will be better to have from the cloud provider side or where we want to run it. 
It's important to keep an eye on them but there are a lot of good tools for it already.
- we can set alerts for high CPU/memory/disk usage or errors in logs - but it depends on our needs, concrete cases
