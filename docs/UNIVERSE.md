# Référentiel MKD — import contrôlé

Format CSV UTF-8 : `symbol,mic,currency,name,asset_type` (ex. `AAPL,XNAS,USD,Apple,equity`).

Dry-run par défaut :
```bash
python -m app.universe universe.csv
```

Écriture uniquement dans la base PostgreSQL MKD :
```bash
python -m app.universe universe.csv --apply
```

Le script refuse les lignes incomplètes, les doublons du manifeste, les identifiants actifs ambigus et les conflits de métadonnées. Il ne se connecte jamais à la base W.

**Limites :** l'inventaire des 806 titres de W n'est pas encore disponible dans ce dépôt. Aucun export W ni contrôle de parité n'a été exécuté. L'import ne résout pas encore les changements historiques de ticker, ISIN et MIC. Les manifests doivent être audités avant application.
