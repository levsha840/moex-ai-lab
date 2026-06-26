# 08_PROJECT_RULES — MOEX AI LAB

## Core Rules
1. CONTROL_CENTER is the only source of current project state.
2. After every completed release, check all 10 CONTROL_CENTER documents.
3. Do not enable live trading by default.
4. Do not commit virtual environments, cache files, logs or generated reports.
5. Every release must include validation commands.
6. Prefer patch-based delivery for multi-file changes.
7. Git working tree should be clean before applying a new release patch.

## Safety Rule
Any module capable of sending live orders must be isolated and disabled unless explicitly enabled.
