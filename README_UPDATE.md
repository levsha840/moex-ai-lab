# PATCH v1.1 — Intraday Data Layer

## Что сделать

1. Распакуй содержимое папки `PATCH_v1.1_Intraday_Data_Layer` поверх проекта:

```text
D:\MOEX_AI
```

2. Разреши замену файлов, если Windows спросит.

3. В VS Code открой терминал в корне проекта и выполни:

```powershell
git status
```

4. Применить SQL:

```powershell
.\scripts\apply_intraday_schema.ps1
```

5. Проверить таблицу:

```powershell
docker exec -it moex_postgres psql -U moex -d moex_ai -c "\dt candles_intraday"
```

6. Запустить тесты:

```powershell
python -m pytest tests/test_intraday_repository.py
python -m pytest
```

## Что прислать в чат

Пришли вывод команд:

```powershell
git status
.\scripts\apply_intraday_schema.ps1
docker exec -it moex_postgres psql -U moex -d moex_ai -c "\dt candles_intraday"
python -m pytest tests/test_intraday_repository.py
```

## Если всё успешно

Коммит:

```powershell
git add .
git commit -m "v1.1 Intraday Data Layer"
git push
```

## Важно

После успешной проверки v1.1 нужно обновить/проверить все 10 документов CONTROL_CENTER.
