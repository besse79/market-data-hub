# MKD V1 — ingestion EOD (première tranche)

`app.ingestion.normalize_bar` contrôle les données OHLCV, les devises, la source et les horodatages.

`app.ingestion.import_bar(session, record)` écrit **uniquement** dans PostgreSQL MKD. L'appelant doit ouvrir et valider/annuler sa transaction. Les doublons strictement identiques sont ignorés ; une correction produit une nouvelle révision, sans effacement.

Contrat de ligne: `instrument_id` UUID existant dans MKD, `session_date` ISO, `provider`, `currency`, `open`, `high`, `low`, `close`, `volume` entier, `published_at` et `first_available_at` ISO avec fuseau.

**Limites actuelles :** aucune collecte Yahoo, aucun import W, aucune planification quotidienne, aucun checkpoint de reprise et aucune sauvegarde/restauration automatisée n'est encore livrée. La validation d'un fournisseur gratuit et des droits de réutilisation précède son branchement. Les tests d'intégration PostgreSQL et la recette WSL sont encore requis. Ne pas basculer W.

Issues: #3, #7, #8, #10. PR #12.

## P0 — provenance Yahoo et verrou PAPER

Les observations Yahoo (y compris la reprise historique) sont systématiquement
insérées avec `quality_status=staged_unverified`. L'heure de capture peut
renseigner `published_at` dans le contrat technique actuel, mais **ne prouve
pas l'heure de publication d'origine**. Elle ne doit jamais servir à
certifier une disponibilité historique point-in-time.

Aucune migration ni requalification des 1 431 039 barres
`legacy_unverified` existantes n'est autorisée par ce changement.
Une validation indépendante et documentée est nécessaire avant toute
promotion de statut. Les consommateurs PAPER doivent rejeter
`staged_unverified` et `legacy_unverified`.

Déploiement : ne pas changer la branche WSL de migration ni lancer
`app.collect_all` en écriture avant une recette PostgreSQL, sauvegarde
vérifiée et contrôle de la sélection des dernières révisions.
