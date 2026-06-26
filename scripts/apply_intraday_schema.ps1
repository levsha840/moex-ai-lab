Get-Content .\infrastructure\intraday_schema.sql | docker exec -i moex_postgres psql -U moex -d moex_ai
