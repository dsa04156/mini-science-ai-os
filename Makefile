SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
export PROJECT_ROOT

.PHONY: help inventory validate bootstrap productize etri-only release-check status demo test destroy-demo rollback build-images portal portfolio-check recovery-plan resilience-plan

help:
	@printf '%s\n' 'make inventory | validate | bootstrap | productize | etri-only | release-check | status | demo | test | destroy-demo | rollback | build-images | portal | portfolio-check | recovery-plan | resilience-plan'

inventory:
	@bash scripts/inventory.sh

validate:
	@bash scripts/validate.sh

build-images:
	@bash scripts/build-images.sh

portal:
	@bash scripts/serve-portals.sh

status:
	@bash scripts/product-status.sh

etri-only:
	@bash scripts/remove-kist.sh

release-check:
	@bash scripts/release-check.sh

productize: bootstrap etri-only release-check

bootstrap:
	@bash scripts/bootstrap.sh

demo:
	@bash scripts/demo.sh

test:
	@bash scripts/test.sh

destroy-demo:
	@bash scripts/destroy-demo.sh

rollback:
	@bash scripts/rollback.sh

portfolio-check:
	@bash portfolio/scripts/test.sh

recovery-plan:
	@bash portfolio/scripts/recovery-drill.sh plan

resilience-plan:
	@bash portfolio/scripts/resilience-drill.sh plan
