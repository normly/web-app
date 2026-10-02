# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

.PHONY: setup dev dev-native dev-attach dev-stop seed seed-local llm-ps llm-logs

setup:
	@./scripts/dev-setup.sh

dev:
	@./scripts/dev-tmux.sh start

dev-native:
	@./scripts/dev-run.sh

dev-attach:
	@./scripts/dev-tmux.sh attach

dev-stop:
	@./scripts/dev-tmux.sh stop

seed:
	@./scripts/seed-data.sh --compose

seed-local:
	@./scripts/seed-data.sh

llm-ps:
	@docker compose --profile chat-llm ps ollama

llm-logs:
	@docker compose --profile chat-llm logs -f ollama
