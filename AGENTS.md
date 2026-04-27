# AGENTS.md

## Project Overview

AI Career Copilot project with:

* Backend: Python (FastAPI)
* Frontend: Vue + Vite
* Test: pytest

---

## Environment Setup

### Python Virtual Environment

Always activate conda environment before running backend or tests:

```powershell
(D:\Anaconda\shell\condabin\conda-hook.ps1)
conda activate rag_workflow
```

---

## Backend (Python)

### Run backend

```powershell
python backend/main.py
```

---

### Run tests

```powershell
pytest backend/test -sv
```

---

## Frontend (Vue + Vite)

### Install dependencies (if needed)

```powershell
cd frontend
npm install
```

### Run frontend

```powershell
cd frontend
npm run dev
```

---

## Critical Rules

* ALWAYS activate conda environment before running Python code
* NEVER run npm commands in project root
* ALL frontend commands MUST be executed inside `/frontend`
* Backend entry is `backend/main.py`
* Tests are located in `backend/test`

---

## Common Issues

### 1. 'vite' not found

Cause: node_modules missing

Fix:

```powershell
cd frontend
npm install
```

---

### 2. Rollup / native module error

Fix:

```powershell
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item -Force package-lock.json
npm cache clean --force
npm install
```

---

### 3. Python cache / temp files

Safe to delete:

```powershell
backend/.pycache_tmp
__pycache__/
```

---

## Agent Behavior Guidelines

* Do NOT ask user how to run environment
* Always follow commands defined in this file
* Prefer existing commands over guessing
* Assume Windows PowerShell environment
* Assume conda is available

---

## Notes

* Frontend and backend are separate; do not mix commands
* Project root does NOT contain package.json
* Always check correct working directory before running commands
