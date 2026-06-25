cd D:\MOEX_AI
Get-ChildItem .\migrations\*.sql | Sort-Object Name | ForEach-Object {
    Write-Host "Applying $($_.Name)"
    Get-Content $_.FullName | docker exec -i moex_postgres psql -U moex -d moex_ai
}
