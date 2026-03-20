# Mission: Traducere MiroFish ZH/EN → RO

## Status
**FAZA:** 1 (Inventar complet) → Pregătire FAZA 2
**Branch:** translate/ro-full

## Inventar Găsit
- **59 fișiere** cu text chinezesc
- **~46,000 caractere chinezești** total

## Fișiere Prioritare

### Frontend Vue (UI utilizator) - ORDINE:
1. Step4Report.vue (1,842 chars)
2. Step2EnvSetup.vue (1,545 chars)
3. Process.vue (1,237 chars)
4. HistoryDatabase.vue (1,209 chars)
5. GraphPanel.vue (919 chars)
6. Step5Interaction.vue (808 chars)
7. Step3Simulation.vue (701 chars)
8. Home.vue (665 chars)
9. SimulationRunView.vue (375 chars)
10. SimulationView.vue (371 chars)
11. Step1GraphBuild.vue (195 chars)
12. ReportView.vue (89 chars)
13. InteractionView.vue (89 chars)
14. MainView.vue (81 chars)
15. App.vue (24 chars)

### Backend Python (LLM Prompts - PRIORITATE MAXIMĂ):
1. **report_agent.py** (7,191 chars) - CRITICAL: PLAN_SYSTEM_PROMPT, SECTION_SYSTEM_PROMPT_TEMPLATE, CHAT_SYSTEM_PROMPT_TEMPLATE
2. **simulation.py** (4,267 chars)
3. **zep_tools.py** (4,071 chars)
4. **simulation_runner.py** (3,141 chars)
5. **oasis_profile_generator.py** (2,911 chars)
6. **simulation_config_generator.py** (2,436 chars) - CRITICAL: system prompts
7. **ontology_generator.py** (1,534 chars) - CRITICAL: prompts LLM
8. **zep_graph_memory_updater.py** (1,418 chars)
9. **graph.py** (758 chars)
10. **simulation_manager.py** (717 chars)

### Documentație:
1. README.md (1,066 chars)
2. README-EN.md (61 chars)

## Glosar Consistent (din CLAUDE.md)
| ZH/EN | RO |
|-------|-----|
| 图谱构建 | Construire graf |
| 知识图谱 | Graf de cunoștințe |
| 环境搭建 | Configurare mediu |
| 模拟/仿真 | Simulare |
| 报告生成 | Generare raport |
| 深度互动 | Interacțiune avansată |
| 智能体/Agent | Agent |
| 实体 | Entitate |
| 节点 | Nod |
| 关系/边 | Relație |
| 舆情 | Opinie publică |
| 推演预测 | Predicție simulativă |
| 群体智能 | Inteligență colectivă |
| 种子信息 | Informație sursă |
| 上帝视角 | Perspectivă globală |
| 数字沙盘 | Sandbox digital |
| Hot Topics | Subiecte fierbinți |
| Narrative Direction | Direcție narativă |
| Ontology | Ontologie |

## Reguli Critice
- ✅ DOAR texte vizibile (UI, mesaje, comentarii, prompt-uri LLM, docstrings)
- ❌ NU traduce: nume variabile, funcții, clase, chei JSON, rute API, importuri
- ❌ NU traduce: logger.debug/info tehnice
- ✅ TRADUCE: prompt-uri LLM (complet și corect)
- ✅ Păstrează formatarea, indentarea, structura
- ✅ Commit atomice: un commit per fișier/grup logic
