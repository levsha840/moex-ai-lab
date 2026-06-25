INSERT INTO strategy_catalog(strategy_name, ticker, version, author, source, status, walkforward_verdict, notes)
SELECT strategy_name, ticker, '1.0', 'human', 'manual', 'active', verdict,
'Imported from strategy_validation_results PASS strategies'
FROM strategy_validation_results
WHERE verdict='PASS'
ON CONFLICT(strategy_name, ticker, version) DO NOTHING;
