# Polymarket Trending Tracker

Application React + FastAPI pour tracker les prédictions Polymarket en temps réel, avec détection automatique des catégories trending et alertes sur les gros shifts de marché.

## Fonctionnalités

- **Extraction automatique des catégories trending** : Agrégation des tags depuis les événements les plus actifs par volume
- **Sélection de catégories** : Interface pour choisir parmi les catégories trending
- **Watchlist** : Page dédiée pour suivre vos prédictions favorites
- **Tracking de marchés** : Ajouter des marchés spécifiques à surveiller
- **Dashboard en temps réel** : Visualisation des probabilités par outcome avec graphiques
- **Alertes intelligentes** : Détection automatique des shifts significatifs avec seuils configurables
- **Quantification des shifts** : Les shifts sont quantifiés par volume impact (magnitude × volume échangé)
- **Historique complet** : Tous les shifts sont conservés en mémoire avec leur volume et impact

## Architecture

- **Backend** : FastAPI avec SQLite (MVP), APScheduler pour les jobs périodiques
- **Frontend** : React + Vite avec React Router
- **API** : Polymarket Gamma API (`gamma-api.polymarket.com`)

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Démarrage

### Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

L'API sera disponible sur `http://localhost:8000`

### Frontend

```bash
cd frontend
npm run dev
```

L'application sera disponible sur `http://localhost:3000`

## Base de données

La base de données SQLite est créée automatiquement au premier démarrage. Si vous avez une ancienne version et que vous avez ajouté de nouvelles colonnes (comme `volume` et `volume_impact` dans la table `alert`), vous pouvez soit :

1. Supprimer le fichier `backend/polymarket_tracker.db` et laisser l'application le recréer
2. Ou exécuter une migration SQL manuelle pour ajouter les colonnes manquantes

## Configuration

Les seuils d'alertes et autres paramètres peuvent être configurés via variables d'environnement ou en modifiant `backend/config.py` :

- `ABSOLUTE_DELTA_THRESHOLD` : Seuil de changement absolu (défaut: 0.05 = 5%)
- `RELATIVE_DELTA_THRESHOLD` : Seuil de changement relatif (défaut: 0.20 = 20%)
- `MIN_VOLUME_THRESHOLD` : Volume minimum pour éviter le bruit (défaut: 100)
- `ALERT_COOLDOWN_MINUTES` : Cooldown entre alertes (défaut: 15 minutes)
- `TRENDING_CATEGORIES_TOP_K` : Nombre de catégories trending à afficher (défaut: 20)

## Pages Frontend

- **Trending** (`/`) : Liste des catégories trending avec recherche
- **Watchlist** (`/watchlist`) : Page dédiée pour suivre vos prédictions avec historique complet des shifts
- **Category** (`/category/:tagSlug`) : Exploration des événements d'une catégorie
- **Dashboard** (`/dashboard`) : Vue d'ensemble avec alertes en temps réel

## Structure du projet

```
.
├── backend/
│   ├── main.py              # FastAPI app
│   ├── database.py          # Modèles SQLAlchemy
│   ├── config.py            # Configuration
│   ├── scheduler.py         # Jobs périodiques
│   └── services/
│       ├── trending_categories.py
│       ├── market_data.py
│       ├── snapshot_service.py
│       └── alert_detection.py
├── frontend/
│   ├── src/
│   │   ├── pages/           # Pages React
│   │   ├── api/             # Clients API
│   │   └── App.jsx
│   └── package.json
└── README.md
```

## Endpoints API

- `GET /api/trending-categories` - Liste des catégories trending
- `GET /api/events?tag_slug=...` - Événements filtrés par catégorie
- `POST /api/tracked-markets` - Ajouter un marché au tracking
- `GET /api/tracked-markets` - Liste des marchés trackés
- `GET /api/markets/{id}/snapshots` - Snapshots historiques
- `GET /api/markets/{id}/shifts` - Tous les shifts d'un marché (triés par impact)
- `GET /api/alerts` - Alertes actives (ou tous avec `include_all=true`)
- `POST /api/alerts/ack/{id}` - Acknowledger une alerte

## Jobs automatiques

- **Refresh trending categories** : Toutes les 10 minutes (configurable)
- **Refresh tracked markets** : Toutes les 5 minutes (configurable)
  - Crée des snapshots pour tous les marchés trackés
  - Détecte les shifts et crée des alertes si nécessaire
