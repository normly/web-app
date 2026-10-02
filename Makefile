# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

.PHONY: dev dev-attach dev-stop

dev:
	@./scripts/dev-tmux.sh start

dev-attach:
	@./scripts/dev-tmux.sh attach

dev-stop:
	@./scripts/dev-tmux.sh stop
