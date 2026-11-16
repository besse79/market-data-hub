# MKD V1 — recette WSL isolée (aucune écriture dans W)

## Préconditions

- Exécuter depuis le dépôt `market-data-hub` sur la branche `feature/v1-foundation`.
- PostgreSQL MKD distinct de W, `DATABASE_URL` pointant **uniquement** vers MKD.
- Un manifeste CSV **explicitement exporté en lecture seule** de W, contenant les colonnes `symbol,mic,currency,name,asset_type`. Le schéma W n'étant pas contractuel, aucun SQL d'export W n'est supposé ici.
- `pg_dump`, `pg_restore`, `psql` et les dépendances Python installés.
- La comparaison historique 806 instruments nécessite un export de référence W daté; l'inventaire MKD seul ne démontre **pas** la parité.

## Exécution contrôlée

Copier le manifeste sous `/tmp/w_instruments.csv`. Depuis la racine MKD :

```bash
set -euo pipefail
test -n "${DATABASE_URL:-}" || { echo "DATABASE_URL MKD absent" >&2; exit 1; }
test -f /tmp/w_instruments.csv
mkdir -p ./artifacts
python -m app.universe /tmp/w_instruments.csv
python -m app.backup "./artifacts/mkd-before-import-$(date -u +%Y%m%dT%H%M%SZ).dump"
python -m app.universe /tmp/w_instruments.csv --apply
python -m app.audit --output ./artifacts/coverage-before.json
```

Le `--apply` est volontairement distinct du contrôle à blanc. Arrêter immédiatement si le nombre d'instruments, les MIC, devises ou métadonnées divergent du manifeste W.

Pour collecter l'historique en lots, choisir une période fixe (fin exclusive). Les appels sont idempotents; un instrument en erreur n'empêche pas les autres et la commande retourne un code non nul si au moins un échoue :

```bash
python -m app.collector --start 2021-11-16 --end 2026-11-16 --limit 100 --offset 0
python -m app.collector --start 2021-11-16 --end 2026-11-16 --limit 100 --offset 100
# Continuer les offsets 200, 300... jusqu'à couvrir le nombre d'identifiants importés.
python -m app.audit --output ./artifacts/coverage-after.json
```

Ne jamais déclarer « 806/806 validés » sur la seule base de ces commandes : vérifier les dates, le nombre de séances, les rejets, les ajustements Yahoo, les devises et les éventuelles révisions contre un export W en lecture seule.

## Test de restauration non destructif

Créer **manuellement** une base PostgreSQL vide dont le nom finit par `_restore_test`, avec les permissions nécessaires; ne jamais réutiliser une base existante. Définir `MKD_RESTORE_TEST_URL` vers cette base, puis :

```bash
python -m app.restore_verify ./artifacts/NOM_DU_DUMP.dump
```

Le script contrôle SHA-256, refuse une cible non vide, et n'efface ni la source ni la cible. Il ne crée et ne supprime aucune base. Comparer ensuite les tables et comptes de lignes source/cible; conserver les preuves CI et locales.

## Critères de clôture

CI verte, migrations aller/retour vérifiées, sauvegarde/restauration sur PostgreSQL isolé, manifeste W vérifié, couverture et rapprochement W/MKD documentés, absence d'écriture dans W, contrats point-in-time et refus des données invalides testés. Tant que la recette WSL et la parité réelle ne sont pas documentées, garder la PR en Draft.
