# MiroFish - Sistem de Predicție și Simulare a Opiniei Publice

## Motor de simulare socială bazat pe multi-agenți

Acest proiect este tradus complet în limba română.

---

## 📋 Cuprins

- [Prezentare generală](#prezentare-generală)
- [Funcționalități](#funcționalități)
- [Arhitectură](#arhitectură)
- [Instalare](#instalare)
- [Configurare](#configurare)
- [Utilizare](#utilizare)
- [Structura proiectului](#structura-proiectului)
- [API](#api)
- [Contribuție](#contribuție)
- [Licență](#licență)

---

## Prezentare generală

MiroFish este un motor avansat de simulare socială care utilizează inteligența artificială și multi-agenți pentru a prezice evoluția opiniei publice și a fenomenelor sociale.

### Caracteristici principale

- **Simulare bazată pe agenți**: Fiecare entitate din sistem are comportamente și memorii unice
- **Graf de cunoștințe**: Relațiile dintre entități sunt modelate ca un graf semantic
- **LLM Integration**: Utilizează modele lingvistice mari pentru generarea de rapoarte și analiză
- **Interfață web modernă**: Frontend Vue 3 cu vizualizări interactive
- **API REST**: Backend Flask pentru integrare ușoară

---

## Funcționalități

### 1. Construire Graf de Cunoștințe
- Extrage automat entități și relații din documente
- Generează ontologie pentru domeniul analizat
- Vizualizare interactivă a grafului

### 2. Configurare Mediu Simulare
- Definește parametrii lumii simulate
- Configurează comportamentele agenților
- Setează reguli de interacțiune

### 3. Rulare Simulare
- Execută simularea în timp real
- Monitorizează progresul și日志
- Controlează viteza și pașii de simulare

### 4. Generare Rapoarte
- Rapoarte automate bazate pe rezultatele simulării
- Analiză detaliată a tendințelor
- Predicții și recomandări

### 5. Interacțiune Avansată
- Conversație cu agenții din simulare
- Interogări în limbaj natural
- Explorare profundă a rezultatelor

---

## Arhitectură

### Frontend (Vue 3)
- **Framework**: Vue 3 + Vite
- **Componente**: Step-based workflow
- **Vizualizare**: D3.js pentru grafuri
- **Stare**: Pinia/Vuex pentru managementul stării

### Backend (Python Flask)
- **Framework**: Flask
- **API**: RESTful endpoints
- **LLM**: Integrare cu modele lingvistice
- **Memorie**: Zep pentru gestionarea memoriei pe termen lung

### Bază de Date
- **Graf**: Stocare entități și relații
- **Memorie**: Fapte și evenimente simulate
- **Persistență**: Date de simulare și rapoarte

---

## Instalare

### Cerințe preliminare

- Python 3.9+
- Node.js 16+
- npm sau yarn
- Git

### Pași de instalare

#### 1. Clonează repository-ul

```bash
git clone https://github.com/antonioeram/MiroFish.git
cd MiroFish
```

#### 2. Instalează dependențele backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# sau
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

#### 3. Instalează dependențele frontend

```bash
cd ../frontend
npm install
```

#### 4. Configurează variabilele de mediu

```bash
# backend/.env
LLM_API_KEY=your_api_key_here
ZEP_BASE_URL=http://localhost:8000
UPLOAD_FOLDER=./uploads
```

---

## Configurare

### Configurare LLM

Editează `backend/app/config.py` pentru a seta:

- Cheia API pentru modelul lingvistic
- URL-ul endpoint-ului LLM
- Parametrii de generare (temperature, max_tokens, etc.)

### Configurare Zep

Zep este utilizat pentru gestionarea memoriei:

```bash
# docker-compose.yml
services:
  zep:
    image: getzep/zep:latest
    ports:
      - "8000:8000"
```

### Configurare Upload

Setează folderul pentru fișierele încărcate în `backend/app/config.py`:

```python
UPLOAD_FOLDER = './uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
```

---

## Utilizare

### 1. Pornire backend

```bash
cd backend
source venv/bin/activate
python run.py
```

Serverul va porni la `http://localhost:5000`

### 2. Pornire frontend

```bash
cd frontend
npm run dev
```

Aplicația va fi disponibilă la `http://localhost:5173`

### 3. Flux de lucru

1. **Încarcă documente** → Construiește graful de cunoștințe
2. **Configurează simularea** → Setează parametrii și agenții
3. **Rulează simularea** → Execută și monitorizează
4. **Generează raport** → Obține analiză și predicții
5. **Interacționează** → Explorează rezultatele prin conversație

---

## Structura proiectului

```
MiroFish/
├── backend/
│   ├── app/
│   │   ├── api/           # Endpoint-uri API
│   │   │   ├── simulation.py
│   │   │   ├── report.py
│   │   │   └── graph.py
│   │   ├── services/      # Servicii business logic
│   │   │   ├── report_agent.py
│   │   │   ├── simulation_runner.py
│   │   │   └── ontology_generator.py
│   │   ├── models/        # Modele de date
│   │   │   ├── project.py
│   │   │   └── task.py
│   │   └── utils/         # Utilitare
│   │       ├── llm_client.py
│   │       └── logger.py
│   ├── scripts/           # Scripturi de rulare
│   ├── run.py             # Entry point
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # Componente Vue
│   │   │   ├── Step1GraphBuild.vue
│   │   │   ├── Step2EnvSetup.vue
│   │   │   ├── Step3Simulation.vue
│   │   │   ├── Step4Report.vue
│   │   │   └── Step5Interaction.vue
│   │   ├── views/         # Pagini
│   │   ├── api/           # Client API
│   │   └── store/         # Management stare
│   ├── index.html
│   └── package.json
├── README.md              # Această documentație
└── CLAUDE.md              # Instrucțiuni agenți AI
```

---

## API

### Endpoint-uri principale

#### Graph API

```
POST   /api/graph/build       # Construiește graf din documente
GET    /api/graph/data        # Obține datele grafului
GET    /api/graph/stats       # Statistici graf
```

#### Simulation API

```
POST   /api/simulation/create     # Creează simulare nouă
POST   /api/simulation/prepare    # Pregătește agenții
POST   /api/simulation/start      # Pornește simularea
GET    /api/simulation/status     # Verifică status
POST   /api/simulation/stop       # Oprește simularea
```

#### Report API

```
POST   /api/report/generate   # Generează raport
GET    /api/report/data       # Obține raportul
GET    /api/report/log        # Log generare raport
```

### Exemplu de utilizare API

```python
import requests

# Construiește graf
response = requests.post('http://localhost:5000/api/graph/build', files={
    'file': open('document.pdf', 'rb')
})
graph_id = response.json()['graph_id']

# Creează simulare
response = requests.post('http://localhost:5000/api/simulation/create', json={
    'graph_id': graph_id,
    'requirement': 'Analizează impactul unei campanii de marketing'
})
simulation_id = response.json()['simulation_id']

# Pornește simularea
requests.post(f'http://localhost:5000/api/simulation/{simulation_id}/start')
```

---

## Depanare

### Probleme comune

#### 1. Eroare la încărcarea fișierelor

**Simptom**: Fișierele nu se încarcă

**Soluție**:
- Verifică permisiunile folderului `uploads/`
- Asigură-te că `MAX_CONTENT_LENGTH` este setat corect
- Verifică spațiul disponibil pe disc

#### 2. LLM nu răspunde

**Simptom**: Timeout la generarea rapoartelor

**Soluție**:
- Verifică cheia API în `.env`
- Asigură-te că endpoint-ul LLM este accesibil
- Crește timeout-ul în configurație

#### 3. Zep nu se conectează

**Simptom**: Erori de memorie

**Soluție**:
- Verifică dacă containerul Zep rulează
- Confirmă URL-ul în configurație
- Restartează serviciul Zep

#### 4. Frontend nu se compilează

**Simptom**: Erori npm run build

**Soluție**:
```bash
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## Contribuție

### Cum să contribui

1. Fork repository-ul
2. Creează un branch pentru funcționalitatea ta (`git checkout -b feature/nume-funcționalitate`)
3. Commit modificările (`git commit -m 'Adaugă funcționalitate X'`)
4. Push la branch (`git push origin feature/nume-funcționalitate`)
5. Deschide un Pull Request

### Standarde de cod

- **Python**: PEP 8
- **JavaScript/Vue**: ESLint + Prettier
- **Commit messages**: Conventional Commits
- **Documentație**: Toate comentariile în română

---

## Licență

Acest proiect este licențiat sub licența MIT. Vezi fișierul `LICENSE` pentru detalii.

---

## Contact

- **Repository**: [github.com/antonioeram/MiroFish](https://github.com/antonioeram/MiroFish)
- **Issues**: [GitHub Issues](https://github.com/antonioeram/MiroFish/issues)

---

## Istoric versiuni

### v2.0 (2026-03-20)
- ✅ Traducere completă în limba română
- ✅ Toate prompt-urile LLM traduse
- ✅ Interfață complet în română
- ✅ Documentație actualizată

### v1.0 (Original)
- Versiunea inițială în chineză/engleză

---

**Notă**: Acest repository este un fork al proiectului original MiroFish, tradus și adaptat pentru utilizatorii vorbitori de limba română.
