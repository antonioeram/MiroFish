# Mission: Traducere MiroFish ZH/EN → RO

## FAZA 0: Setup ✅
- [x] Creat branch `translate/ro-full`
- [x] Verificat starea repository-ului

## FAZA 1: Inventar ✅
- [x] Scanat toate fișierele
- [x] Inventar complet: 59 fișiere, ~46,000 caractere chinezești
- [x] Salvat în `.opencode/full-inventory.txt`

## FAZA 2: Traducere Frontend (Vue + JS)

### P2.1: Componente Vue Prioritare | agent:Worker
- [ ] Step4Report.vue (1,842 chars) | file:frontend/src/components/Step4Report.vue
- [ ] Step2EnvSetup.vue (1,545 chars) | file:frontend/src/components/Step2EnvSetup.vue
- [ ] Process.vue (1,237 chars) | file:frontend/src/views/Process.vue
- [ ] HistoryDatabase.vue (1,209 chars) | file:frontend/src/components/HistoryDatabase.vue
- [ ] GraphPanel.vue (919 chars) | file:frontend/src/components/GraphPanel.vue
- [ ] Step5Interaction.vue (808 chars) | file:frontend/src/components/Step5Interaction.vue
- [ ] Step3Simulation.vue (701 chars) | file:frontend/src/components/Step3Simulation.vue
- [ ] Home.vue (665 chars) | file:frontend/src/views/Home.vue

### P2.2: Alte Componente Vue | agent:Worker
- [ ] SimulationRunView.vue (375 chars) | file:frontend/src/views/SimulationRunView.vue
- [ ] SimulationView.vue (371 chars) | file:frontend/src/views/SimulationView.vue
- [ ] Step1GraphBuild.vue (195 chars) | file:frontend/src/components/Step1GraphBuild.vue
- [ ] ReportView.vue (89 chars) | file:frontend/src/views/ReportView.vue
- [ ] InteractionView.vue (89 chars) | file:frontend/src/views/InteractionView.vue
- [ ] MainView.vue (81 chars) | file:frontend/src/views/MainView.vue
- [ ] App.vue (24 chars) | file:frontend/src/App.vue
- [ ] index.html (14 chars) | file:frontend/index.html

### P2.3: Fișiere JavaScript | agent:Worker
- [ ] simulation.js (222 chars) | file:frontend/src/api/simulation.js
- [ ] index.js (69 chars) | file:frontend/src/api/index.js
- [ ] graph.js (47 chars) | file:frontend/src/api/graph.js
- [ ] report.js (54 chars) | file:frontend/src/api/report.js
- [ ] store/pendingUpload.js (36 chars) | file:frontend/src/store/pendingUpload.js
- [ ] main.js | file:frontend/src/main.js
- [ ] router/index.js | file:frontend/src/router/index.js

## FAZA 3: Traducere Backend (Python)

### P3.1: LLM Prompts (PRIORITATE MAXIMĂ) | agent:Worker
- [ ] report_agent.py (7,191 chars) | file:backend/app/services/report_agent.py
- [ ] simulation_config_generator.py (2,436 chars) | file:backend/app/services/simulation_config_generator.py
- [ ] ontology_generator.py (1,534 chars) | file:backend/app/services/ontology_generator.py

### P3.2: Servicii Backend Principale | agent:Worker
- [ ] simulation.py (4,267 chars) | file:backend/app/api/simulation.py
- [ ] zep_tools.py (4,071 chars) | file:backend/app/services/zep_tools.py
- [ ] simulation_runner.py (3,141 chars) | file:backend/app/services/simulation_runner.py
- [ ] oasis_profile_generator.py (2,911 chars) | file:backend/app/services/oasis_profile_generator.py
- [ ] run_parallel_simulation.py (2,814 chars) | file:backend/scripts/run_parallel_simulation.py
- [ ] zep_graph_memory_updater.py (1,418 chars) | file:backend/app/services/zep_graph_memory_updater.py
- [ ] run_twitter_simulation.py (1,159 chars) | file:backend/scripts/run_twitter_simulation.py
- [ ] report.py (1,069 chars) | file:backend/app/api/report.py
- [ ] run_reddit_simulation.py (1,032 chars) | file:backend/scripts/run_reddit_simulation.py

### P3.3: Alte Servicii Backend | agent:Worker
- [ ] graph.py (758 chars) | file:backend/app/api/graph.py
- [ ] simulation_manager.py (717 chars) | file:backend/app/services/simulation_manager.py
- [ ] zep_entity_reader.py (695 chars) | file:backend/app/services/zep_entity_reader.py
- [ ] graph_builder.py (555 chars) | file:backend/app/services/graph_builder.py
- [ ] simulation_ipc.py (548 chars) | file:backend/app/services/simulation_ipc.py
- [ ] project.py (359 chars) | file:backend/app/models/project.py
- [ ] retry.py (288 chars) | file:backend/app/utils/retry.py
- [ ] file_parser.py (268 chars) | file:backend/app/utils/file_parser.py
- [ ] action_logger.py (254 chars) | file:backend/scripts/action_logger.py
- [ ] logger.py (206 chars) | file:backend/app/utils/logger.py
- [ ] test_profile_format.py (183 chars) | file:backend/scripts/test_profile_format.py
- [ ] task.py (175 chars) | file:backend/app/models/task.py
- [ ] __init__.py (154 chars) | file:backend/app/__init__.py
- [ ] config.py (138 chars) | file:backend/app/config.py
- [ ] zep_paging.py (113 chars) | file:backend/app/utils/zep_paging.py
- [ ] llm_client.py (107 chars) | file:backend/app/utils/llm_client.py
- [ ] text_processor.py (101 chars) | file:backend/app/services/text_processor.py
- [ ] run.py (90 chars) | file:backend/run.py
- [ ] __init__.py servicii (6 chars) | file:backend/app/services/__init__.py
- [ ] __init__.py modele (6 chars) | file:backend/app/models/__init__.py
- [ ] __init__.py utils (4 chars) | file:backend/app/utils/__init__.py
- [ ] __init__.py api (4 chars) | file:backend/app/api/__init__.py

## FAZA 4: Documentație | agent:Worker
- [ ] README.md (1,066 chars) | file:README.md
- [ ] README-EN.md (61 chars) | file:README-EN.md

## FAZA 5: Verificare | agent:Reviewer
- [ ] Verificare texte chineze rămase
- [ ] Compilare Python
- [ ] Build frontend
- [ ] Testare funcțională

## FAZA 6: Push | agent:Commander
- [ ] Push branch translate/ro-full
