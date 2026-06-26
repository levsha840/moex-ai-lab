# PATCH v1.2 — Feature Factory

## Что добавлено

- `core/features/technical_indicators.py` — базовые технические индикаторы.
- `core/features/feature_factory.py` — фабрика признаков по OHLCV-свечам.
- `tests/test_feature_factory.py` — тесты Feature Factory.
- Обновлены документы `CONTROL_CENTER` под состояние v1.2.

## Как применить

Распаковать содержимое архива поверх корня проекта:

```powershell
D:\MOEX_AI
```

## Проверка

```powershell
python -m pytest tests/test_feature_factory.py
python -m pytest tests/test_intraday_repository.py tests/test_feature_factory.py
```

## Если тесты прошли

```powershell
git status
git add .
git commit -m "v1.2 Feature Factory"
git push
```

## Критерий готовности

- Все тесты Feature Factory проходят.
- Ранее добавленные тесты Intraday Repository не сломаны.
- `CONTROL_CENTER` обновлен.
