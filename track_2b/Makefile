.PHONY: run test

IMAGE := apertus-flowguard:local

run:
	docker build --tag $(IMAGE) .
	docker run --rm \
		--env LLM_NAME --env LLM_BASE_URL --env LLM_API_KEY \
		--env FLOWGUARD_QUESTION --env FLOWGUARD_INPUT_JSON \
		$(IMAGE)

test:
	python3 -m unittest discover -s src -p 'test_*.py' -v
