# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Build definition for the image pipeline (.github/workflows/images.yml).
# One `docker buildx bake` builds all five images in a single BuildKit
# session, so the four Python targets share their deps/weights/base layers.
# compose.yaml keeps its own build: blocks for `docker compose up --build`;
# both point at the same Dockerfiles and targets.
#
# Variables (all optional locally):
#   REGISTRY   image name prefix
#   TAGS       space-separated tags applied to every image
#   CACHE_REF  registry cache prefix; empty disables the registry cache
#   PUSH       "1" when pushing: enables provenance + SBOM attestations
#              (the local docker exporter cannot store them)

variable "REGISTRY" { default = "ghcr.io/normly/web-app" }
variable "TAGS" { default = "local" }
variable "CACHE_REF" { default = "" }
variable "PUSH" { default = "0" }

function "tags" {
  params = [name]
  result = [for t in split(" ", TAGS) : "${REGISTRY}/${name}:${t}"]
}

function "cache_from" {
  params = [name]
  result = CACHE_REF == "" ? [] : ["type=registry,ref=${CACHE_REF}:${name}"]
}

function "cache_to" {
  params = [name]
  result = CACHE_REF == "" ? [] : ["type=registry,ref=${CACHE_REF}:${name},mode=max"]
}

group "default" {
  targets = ["api", "chat", "accounts", "pipeline", "frontend"]
}

target "_common" {
  platforms = ["linux/amd64"]
  attest = PUSH == "1" ? ["type=provenance,mode=max", "type=sbom"] : []
}

target "_python" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "docker/python.Dockerfile"
}

target "api" {
  inherits   = ["_python"]
  target     = "api"
  tags       = tags("api")
  cache-from = cache_from("api")
  cache-to   = cache_to("api")
}

target "chat" {
  inherits   = ["_python"]
  target     = "chat"
  tags       = tags("chat")
  cache-from = cache_from("chat")
  cache-to   = cache_to("chat")
}

target "accounts" {
  inherits   = ["_python"]
  target     = "accounts"
  tags       = tags("accounts")
  cache-from = cache_from("accounts")
  cache-to   = cache_to("accounts")
}

target "pipeline" {
  inherits   = ["_python"]
  target     = "pipeline"
  tags       = tags("pipeline")
  cache-from = cache_from("pipeline")
  cache-to   = cache_to("pipeline")
}

target "frontend" {
  inherits   = ["_common"]
  context    = "frontend"
  dockerfile = "Dockerfile"
  tags       = tags("frontend")
  cache-from = cache_from("frontend")
  cache-to   = cache_to("frontend")
}
