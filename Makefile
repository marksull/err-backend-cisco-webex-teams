CONTAINER_NAME = err-teams
ENV_FILE= --env-file .env.local
DOCKER_RUN = docker run -it --rm $(ENV_FILE)

.PHONY: build run sh

build:
	docker build . -t $(CONTAINER_NAME)

run:
	$(DOCKER_RUN) $(CONTAINER_NAME)

sh:
	$(DOCKER_RUN) --entrypoint sh $(CONTAINER_NAME)
