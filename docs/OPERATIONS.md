# MKD — opérations de sécurité

## Préconditions

MKD utilise sa propre base PostgreSQL, séparée de Weinstein'S.
`DATABASE_URL` doit pointer explicitement vers la base MKD.
Ne jamais exécuter de restauration sur la base W.

## Sauvegarde

```bash
python -m app.backup backups/mkd-$(date -u +%Y%m%dT%H%M%SZ).dump
```

La commande échoue si le fichier existe déjà. Elle vérifie le catalogue
`pg_restore --list` et produit un SHA-256 à côté du dump. Elle nécessite
`pg_dump` et `pg_restore` installés localement.

## Restauration

Aucune restauration automatique n'est proposée. Pour une recette, créer une
**nouvelle base PostgreSQL vide**, vérifier le SHA-256 et tester le dump avec
`pg_restore --no-owner --no-acl --dbname=<URL_DE_LA_BASE_DE_TEST> fichier.dump`.
Ne jamais restaurer directement dans W ou écraser la base MKD de production.

## Validation avant bascule W

1. Exporter le référentiel W dans un CSV explicite (symbol,mic,currency,name,asset_type).
2. Contrôler l'import : `python -m app.universe universe.csv`.
3. Importer uniquement après validation : `python -m app.universe universe.csv --apply`.
4. Comparer : `python -m app.reconcile universe.csv --output rapprochement.json`.
5. Collecter sur une fenêtre limitée, puis étendre par lots.
6. Comparer les OHLCV, dates, devises et volumes à W sur les 806 titres et benchmarks.
7. Tester sauvegarde/restauration sur une base isolée avant de brancher W.

Le statut de ces opérations reste **non vérifié sur WSL** jusqu'à exécution réelle.
