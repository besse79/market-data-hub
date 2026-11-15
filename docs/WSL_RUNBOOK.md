# MKD V1 — recette WSL sans écriture dans Weinstein'S

**Statut** : procédure à exécuter sur le poste WSL. Une CI verte ne démontre pas la parité des 806 instruments W.

## Prérequis

- Dépôt MKD cloné, Python 3.12, PostgreSQL et utilitaires `pg_dump`, `pg_restore`, `psql`.
- `DATABASE_URL` pointe **uniquement** vers la base PostgreSQL MKD (jamais vers W).
- Installer les dépendances : `python -m pip install -e '.[test]'`.
- Créer la base MKD séparée, puis `alembic upgrade head`.
- Générer hors MKD un manifeste CSV en lecture seule depuis W, avec les colonnes exactes `symbol,mic,currency,name,asset_type`. Le programme MKD ne doit recevoir **aucun identifiant de connexion W**. Conserver une empreinte SHA-256 du manifeste et une preuve de non-modification de W.
- Ne pas inventer le MIC ni la devise d'un titre : les lignes ambiguës doivent être mises en quarantaine.

## Exécution contrôlée

1. Vérifier le manifeste : `python -m app.universe /chemin/manifest.csv` (simulation, aucune écriture).
2. Sauvegarder MKD avant import : `python -m app.backup /chemin/mkd-before-import.dump`.
3. Importer **dans MKD uniquement** : `python -m app.universe /chemin/manifest.csv --apply`.
4. Collecter un premier lot, puis reprendre les suivants sans écraser l'historique : `python -m app.collector --start 2025-01-01 --end 2026-11-16 --limit 100 --offset 0 --delay 1`. Reprendre avec offsets 100, 200, etc. Les erreurs par instrument sont signalées et provoquent un code retour non nul.
5. Exporter la couverture : `python -m app.audit --minimum-sessions 1000 --output /chemin/mkd-coverage.json`.
6. Contrôler les 806 titres **par identifiant symbol + MIC + devise**, les doublons, les historiques courts, les rejets, les dates manquantes et les écarts OHLCV avec W. Une couverture suffisante ne prouve pas la parité des cours. Consigner les écarts dans un rapport distinct.
7. Créer une base PostgreSQL vide et isolée dont le nom se termine par `_restore_test`. Fournir `MKD_RESTORE_TEST_URL` (URL de cette base), puis exécuter `python -m app.restore_verify /chemin/mkd-before-import.dump`. Ne jamais utiliser la base W comme cible.

## Critères de clôture

- CI verte incluant tests PostgreSQL et restauration réelle ; migration aller-retour.
- Manifeste des 806 instruments vérifié et import idempotent ; aucune écriture W.
- Historique quotidien exploitable avec rejets documentés, dates et volumes cohérents.
- Rapprochement W/MKD sur données réelles avec écarts justifiés et acceptés.
- Lecture seule depuis les consommateurs W/QE/B, contrôle des dates de disponibilité point-in-time.
- Preuves de sauvegarde, checksum et restauration dans une base isolée.

**Interdiction** : ne pas déclarer la V1 livrée sur la seule base d'une CI verte ou d'un audit de couverture.
