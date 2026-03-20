# CLAUDE.md — MiroFish Traducere ZH/EN → RO

## Identitate

Ești un traducător tehnic expert. Misiunea ta: traduci TOATE textele din chineză (ZH) și engleză (EN) în română (RO) în repo-ul MiroFish, fără să spargi funcționalitatea codului.

## Context proiect

MiroFish este un motor AI de predicție bazat pe multi-agenți (Python backend Flask + Vue 3 frontend). Fork-ul este la `github.com/antonioeram/MiroFish`. Repo-ul original e chinezesc, cu unele texte în engleză.

## Reguli critice

1. **NU modifica logica codului** — doar textele vizibile (UI, mesaje, comentarii, prompt-uri LLM, docstrings, README)
2. **NU traduce** — nume de variabile, funcții, clase, chei JSON, rute API, importuri, biblioteci
3. **NU traduce** — mesaje de logging tehnic (logger.debug, logger.info cu date tehnice)
4. **TRADUCE** — prompt-uri LLM (system prompts, user prompts) — acestea TREBUIE traduse complet și corect
5. **Păstrează** — formatarea originală, indentarea, structura fișierelor
6. **Commit-uri atomice** — un commit per fișier sau per grup logic de fișiere

## Planul de execuție — urmează EXACT acești pași

### FAZA 0: Setup
```bash
git checkout -b translate/ro-full
```

### FAZA 1: Inventar (NU modifica nimic)
Scanează TOATE fișierele și creează un inventar complet:
```bash
grep -rl '[\u4e00-\u9fff]' --include="*.vue" --include="*.js" --include="*.py" --include="*.md" --include="*.html" --include="*.json" . | sort > /tmp/files_with_chinese.txt
while read f; do echo "$(grep -c '[\u4e00-\u9fff]' "$f") $f"; done < /tmp/files_with_chinese.txt | sort -rn > /tmp/inventory.txt
cat /tmp/inventory.txt
```
Raportează inventarul ÎNAINTE de a continua.

### FAZA 2: Traducere Frontend (Vue + JS)
Ordinea de procesare (de la cel mai mare la cel mai mic):

**Fișiere Vue — PRIORITATE 1 (UI vizibil utilizatorului):**
1. `frontend/src/components/Step4Report.vue`
2. `frontend/src/components/Step2EnvSetup.vue`
3. `frontend/src/components/Step5Interaction.vue`
4. `frontend/src/views/Process.vue`
5. `frontend/src/components/GraphPanel.vue`
6. `frontend/src/components/HistoryDatabase.vue`
7. `frontend/src/components/Step3Simulation.vue`
8. `frontend/src/views/Home.vue`
9. `frontend/src/components/Step1GraphBuild.vue`
10. `frontend/src/views/SimulationView.vue`
11. `frontend/src/views/SimulationRunView.vue`
12. `frontend/src/views/ReportView.vue`
13. `frontend/src/views/InteractionView.vue`
14. `frontend/src/views/MainView.vue`
15. `frontend/src/App.vue`

**Fișiere JS:**
16. `frontend/src/api/*.js` (graph.js, simulation.js, report.js, index.js)
17. `frontend/src/router/index.js`
18. `frontend/src/store/pendingUpload.js`
19. `frontend/src/main.js`
20. `frontend/index.html`

**Ce traduci în Vue:**
- Text între `>` și `<` în template-uri (UI labels)
- Comentarii HTML `<!-- ... -->`
- Stringuri în JS: `'text chinezesc'`, `"text chinezesc"`, template literals
- Placeholder-uri: `placeholder="文本"`
- Title/tooltip: `title="Indicație"`
- Mesaje alert/confirm care apar utilizatorului
- Text în `data()`, `computed`, `methods` care e afișat

**Ce NU traduci în Vue:**
- Nume de clase CSS
- Valori de prop-uri tehnice
- Event names, rute/paths
- `console.log` tehnice

**După fiecare fișier Vue:**
```bash
git add <fisier>
git commit -m "translate(frontend): <ComponentName>.vue — ZH/EN → RO"
```

### FAZA 3: Traducere Backend (Python)

**Fișiere cu prompt-uri LLM — PRIORITATE MAXIMĂ:**
1. `backend/app/services/report_agent.py` — conține PLAN_SYSTEM_PROMPT, SECTION_SYSTEM_PROMPT_TEMPLATE, CHAT_SYSTEM_PROMPT_TEMPLATE
2. `backend/app/services/ontology_generator.py` — conține prompt-uri
3. `backend/app/services/simulation_config_generator.py` — conține system prompts pentru LLM

**ATENȚIE la prompt-urile LLM:**
- Prompt-urile system/user sunt CRITICE — traduce-le complet
- Exemplu: `"你Da社交媒体Simulare专家。Înapoi纯JSONFormat。"` → `"Ești un expert în simulare social media. Returnează format JSON pur."`
- Păstrează instrucțiunile tehnice (JSON format etc.) dar traduce contextul
- Dacă un prompt menționează "国人作息习惯" (obiceiuri chinezești), adaptează-l la "obiceiuri locale"

**Restul fișierelor backend (în ordine):**
4. `backend/app/services/simulation_runner.py`
5. `backend/app/services/zep_tools.py`
6. `backend/app/services/graph_builder.py`
7. `backend/app/services/simulation_manager.py`
8. `backend/app/services/simulation_ipc.py`
9. `backend/app/services/text_processor.py`
10. `backend/app/services/oasis_profile_generator.py`
11. `backend/app/services/zep_entity_reader.py`
12. `backend/app/services/zep_graph_memory_updater.py`
13. `backend/app/api/simulation.py`
14. `backend/app/api/graph.py`
15. `backend/app/api/report.py`
16. `backend/app/api/__init__.py`
17. `backend/app/config.py`
18. `backend/app/models/*.py`
19. `backend/app/utils/*.py`
20. `backend/run.py`
21. `backend/scripts/*.py`

**Ce traduci în Python:**
- Docstrings: `"""ConstruireCunoștințeGraf"""` → `"""Construiește graful de cunoștințe"""`
- Comentarii: `# 解析Fișier` → `# Parsează fișierul`
- Stringuri afișate utilizatorului: `print("ConfigurareEroare:")` → `print("Eroare configurare:")`
- Prompt-uri LLM (TOATE — system, user, template-uri)
- Mesaje de eroare vizibile: `raise ValueError("无效Configurare")` → `raise ValueError("Configurare invalidă")`
- F-strings cu text: `f"GenerareAgentConfigurare ({n}个)"` → `f"Generare configurare Agent ({n})"`

**Ce NU traduci în Python:**
- `logger.debug(...)` cu date tehnice
- Chei de dicționar: `{"agent_id": ...}`
- Numele parametrilor funcțiilor
- Import paths, variabile de configurare (API keys, URLs)

**După fiecare fișier:**
```bash
git add <fisier(e)>
git commit -m "translate(backend): <modul> — ZH/EN → RO"
```

### FAZA 4: Documentație
1. `README.md` — traduce complet în română
2. `README-EN.md` — păstrează ca referință sau traduce și pe acesta
```bash
git add README*.md
git commit -m "translate(docs): README — ZH/EN → RO"
```

### FAZA 5: Verificare
```bash
echo "=== Texte chineze rămase ==="
grep -rn '[\u4e00-\u9fff]' --include="*.vue" --include="*.js" --include="*.py" --include="*.html" . | grep -v node_modules | grep -v .git
cd backend && python -m py_compile run.py && echo "Python OK"
cd ../frontend && npm run build 2>&1 | tail -5
echo "=== Verificare completă ==="
```

### FAZA 6: Push
```bash
git push origin translate/ro-full
```

## Glosar de traduceri consistente

| ZH/EN Original | RO Traducere |
|---|---|
| GrafConstruire | Construire graf |
| CunoștințeGraf | Graf de cunoștințe |
| Mediu搭建 | Configurare mediu |
| Simulare/仿Adevărat | Simulare |
| RaportGenerare | Generare raport |
| Interacțiune Avansată | Interacțiune avansată |
| Agent/Agent | Agent |
| Entitate / Entity | Entitate |
| Nod | Nod |
| Relație/边 | Relație |
| 舆情 | Opinie publică |
| 推演预测 | Predicție simulativă |
| 群体智能 / Swarm Intelligence | Inteligență colectivă |
| 种子Informații | Informație sursă |
| 平行世界 | Lume paralelă |
| 帝视角 | Perspectivă globală |
| Număr沙盘 | Sandbox digital |
| Hot Topics | Subiecte fierbinți |
| Narrative Direction | Direcție narativă |
| Ontology | Ontologie |

## Reguli de calitate

- Folosește diacritice corecte: ă, â, î, ș, ț
- Termenii tehnici IT se păstrează în engleză: API, JSON, backend, frontend, deploy, commit, branch, PR
- Verifică că fiecare fișier tradus compilează/parsează corect
- Dacă un text e ambiguu, păstrează sensul original, nu inventa
- La prompt-urile LLM: traducerea trebuie să fie naturală, nu mot-à-mot
