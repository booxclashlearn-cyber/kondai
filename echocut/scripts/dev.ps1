param([ValidateSet("setup","dev","test","lint","typecheck","migrate","seed","build","down")][string]$Task="dev")
$root=Split-Path $PSScriptRoot -Parent
switch($Task){
 "setup" { Copy-Item "$root/.env.example" "$root/.env" -ErrorAction SilentlyContinue; python -m pip install -r "$root/backend/requirements.txt"; npm.cmd --prefix "$root/frontend" install }
 "dev" { docker compose --project-directory $root up --build }
 "test" { Push-Location "$root/backend"; pytest; Pop-Location; npm.cmd --prefix "$root/frontend" test }
 "lint" { Push-Location "$root/backend"; ruff check .; Pop-Location; npm.cmd --prefix "$root/frontend" run lint }
 "typecheck" { npm.cmd --prefix "$root/frontend" run typecheck }
 "migrate" { Push-Location "$root/backend"; python -m alembic upgrade head; Pop-Location }
 "seed" { Push-Location "$root/backend"; python -m app.seed; Pop-Location }
 "build" { npm.cmd --prefix "$root/frontend" run build; docker compose --project-directory $root build }
 "down" { docker compose --project-directory $root down }
}
