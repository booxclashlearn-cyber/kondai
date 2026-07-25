$ErrorActionPreference = "Stop"

Write-Host "Checking loaded backend build..."
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/cors-status" | ConvertTo-Json -Depth 5

Write-Host "`nChecking preflight from Vite..."
curl.exe -i -X OPTIONS "http://localhost:8000/api/v1/onboarding/status" `
  -H "Origin: http://localhost:5173" `
  -H "Access-Control-Request-Method: GET" `
  -H "Access-Control-Request-Headers: x-user-id,x-workspace-id,content-type"
