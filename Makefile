CONTAINER_NAME = err-teams:local
CONTAINER_NAME_TEST = err-teams-test:local
ENV_FILE= --env-file .env.local
DOCKER_RUN = docker run -it --rm $(ENV_FILE)

.PHONY: build run sh test_build test_run test_sh test_build_run

build:
	docker build -t $(CONTAINER_NAME) .

run:
	$(DOCKER_RUN) $(CONTAINER_NAME)

sh:
	$(DOCKER_RUN) --entrypoint sh $(CONTAINER_NAME)

test_build:
	make build
	# https://github.com/docker/compose/issues/8449
	DOCKER_BUILDKIT=0 docker build --pull=false -f Dockerfile.test -t $(CONTAINER_NAME_TEST) .

test_run:
	$(DOCKER_RUN) $(CONTAINER_NAME_TEST)

test_sh:
	$(DOCKER_RUN) --entrypoint sh $(CONTAINER_NAME_TEST)

test_build_run:
	make test_build
	make test_run
