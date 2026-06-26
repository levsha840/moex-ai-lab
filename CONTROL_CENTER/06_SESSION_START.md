# 06_SESSION_START — MOEX AI LAB

## Как продолжить работу

Текущее состояние:

- `v1.1 Intraday Data Layer` завершен.
- `v1.2 Feature Factory` завершен.
- Следующий релиз: `v1.3 Intraday Dataset Builder / Replay Integration`.

## Первые команды в новой сессии

```powershell
git status
python -m pytest tests/test_intraday_repository.py tests/test_feature_factory.py
```

## Что делать дальше

Начать разработку `v1.3`:

1. Создать dataset builder.
2. Получать intraday-свечи через репозиторий.
3. Пропускать данные через Feature Factory.
4. Проверить pipeline тестом.

## Важное правило

Перед новым релизом рабочее дерево Git должно быть чистым.
