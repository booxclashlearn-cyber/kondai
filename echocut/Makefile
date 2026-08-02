.PHONY: setup dev test lint typecheck migrate seed build down
setup:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
dev:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 dev
test:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 test
lint:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 lint
typecheck:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 typecheck
migrate:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
seed:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
build:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 build
down:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 down

