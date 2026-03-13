# ServVia Neuro-Symbolic AI Healthcare

This repository contains the ServVia AI Healthcare platform — a privacy-first clinical assistant built with Django, LangGraph, and multi-agent AI.

## Repository Structure

### ServVia (AI Healthcare Server)

The core ServVia AI assistant. Handles clinical conversations, lab report analysis, pharmacovigilance, chronobiology-aware dosing, and skin disease detection.

- **Path:** `./servvia/`
- **Port:** `9000`
- **Start:** `cd servvia && python manage.py runserver 0.0.0.0:9000`

### ServVia Backend (Data Platform)

The data platform backend. Manages datasets, connectors, participants, and knowledge base APIs consumed by the ServVia AI server.

- **Path:** `./servvia-backend/`
- **Port:** `9001`
- **Start:** `cd servvia-backend && python manage.py runserver 0.0.0.0:9001`

## Getting Started

```bash
git clone https://github.com/digitalgreenorg/monorepo.git
```

## Support

- **Issue Tracker:** https://github.com/digitalgreenorg/monorepo/issues
- **Email:** support@digitalgreen.org
