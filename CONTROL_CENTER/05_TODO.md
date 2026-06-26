# 05_TODO — MOEX AI LAB

## Следующий релиз: v1.3 Intraday Dataset Builder / Replay Integration

### Основные задачи

- [ ] Создать модуль построения датасета из `candles_intraday`.
- [ ] Подключить `IntradayRepository` к `FeatureFactory`.
- [ ] Добавить фильтрацию по тикеру и диапазону дат.
- [ ] Подготовить формат dataset rows для AI/replay.
- [ ] Добавить smoke-тест полного pipeline.
- [ ] Обновить `CONTROL_CENTER` после завершения.

## Позже

- [ ] Добавить pandas adapter, если потребуется.
- [ ] Добавить сохранение рассчитанных признаков в БД.
- [ ] Добавить target labeling для обучения.
- [ ] Добавить feature quality checks.
