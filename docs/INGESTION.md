# MKD V1 — ingestion EOD (première tranche)

`app.ingestion.normalize_bar` contrôle les données OHLCV, les devises, la source et les horodatages.

`app.ingestion.import_bar(session, record)` écrit **uniquement** dans PostgreSQL MKD. L'appelant doit ouvrir et valider/annuler sa transaction. Les doublons strictement identiques sont ignorés ; une correction produit une nouvelle révision, sans effacement.

Contrat de ligne: `instrument_id` UUID existant dans MKD, `session_date` ISO, `provider`, `currency`, `open`, `high`, `low`, `close`, `volume` entier, `published_at` et `first_available_at` ISO avec fuseau.

**Limites actuelles :** aucune collecte Yahoo, aucun import W, aucune planification quotidienne, aucun checkpoint de reprise et aucune sauvegarde/restauration automatisée n'est encore livrée. La validation d'un fournisseur gratuit et des droits de réutilisation précède son branchement. Les tests d'intégration PostgreSQL et la recette WSL sont encore requis. Ne pas basculer W.

Issues: #3, #7, #8, #10. PR #12.
