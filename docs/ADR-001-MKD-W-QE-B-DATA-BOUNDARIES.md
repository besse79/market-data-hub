# ADR-001 — Mutualisation des données de marché, périmètre et nomenclature

**Statut : proposé pour validation.** Date : 2026-11-15.
**Décision : ne modifier aucun schéma existant des applications consommatrices avant une recette de parité.**

## Nomenclature officielle

| Code | Produit | Dépôt GitHub | Responsabilité |
|---|---|---|---|
| **MKD** | MarketDataHub | `besse79/market-data-hub` | Données financières communes, qualité, provenance, FX |
| **W** | Weinstein'S | `besse79/cto-weinstein-trader` | Scanner Weinstein, stratégie, portefeuille et ordres PAPER |
| **QE** | QuantEdge | `besse79/QuantEdge` | Modèles quantitatifs, stratégies, signaux et portefeuilles propres |
| **B** | BuffettValue | `besse79/BuffettValue` | Valorisation fondamentale, DCF et portefeuille propre |

Les **codes sont des alias fonctionnels**, pas des instructions de renommer les dépôts.

## Architecture et frontières de responsabilité

```text
Sources gratuites autorisées (Yahoo EOD, SEC EDGAR, FX à qualifier)
                           |
                           v
                MKD — ingestion / qualité
                PostgreSQL MKD propre
     instruments, identifiants, prix EOD, actions de
     société, univers datés, fondamentaux, FX,
       provenance, publications et versionnage
                           |
                   API FastAPI /v1
              lecture seule, date as_of
                  /       |       \
                 v        v        v
                 W        QE       B
              DB W       DB QE    DB B
        stratégies, signaux, ordres/portefeuilles PAPER,
        limites de risque, métriques métier et historique
```

**Invariants :**
1. MKD n'enregistre **aucun ordre, stop, position ou solde de portefeuille** ; ces données restent propres à W/QE/B.
2. Les identifiants MKD sont stables et indépendants des symboles Yahoo. Les changements de ticker, ISIN, place (MIC) et devise sont historisés.
3. Aucun changement de schéma ni migration automatique du PostgreSQL W existant. Aucun remplacement des 806 historiques EUR/USD déjà importés sans comparaison détaillée puis décision explicite.
4. Les consommateurs ne reçoivent pas des cours invalides, provisoires ou futurs comme s'ils étaient certifiés. Toutes les réponses portent les métadonnées de qualité, source, horodatage, devise et disponibilité.
5. Les contrats exposent des données disponibles **à la date de décision** (`as_of`), pas les révisions récentes recollées silencieusement au passé.
6. Les API gratuites restent soumises à leurs quotas et conditions d'usage ; pas de contournement des refus fournisseurs.

## Données MKD V1 : schéma PostgreSQL à implémenter DANS MKD, pas dans W

- `instruments` : clé stable, nom, type, devise de cotation, statut, place principale, pays.
- `instrument_identifiers` : symbole fournisseur/MIC/ISIN, validité `valid_from`/`valid_to`, source et unicité temporelle contrôlée.
- `eod_bars` : instrument, séance locale, OHLCV natifs, devise, source, données ajustées distinctes, `published_at`, `ingested_at`, `effective_at`, version/révision et qualité; unicité contrôlée sans écrasement silencieux.
- `corporate_actions` : splits, dividendes et leurs dates `ex_date`, `published_at`, `ingested_at`.
- `index_constituents` : snapshots datés et provenance; un snapshot de 2026 ne prouve pas l'appartenance en 2021.
- `fx_eod` : paire de devises, sens explicite (ex. EUR/USD = nombre de USD pour 1 EUR), taux, date de référence, publication, collecte, source, validation, révision; **EUR et USD prioritaires**.
- `data_quality_events` / `ingestion_runs` : anomalies bloquantes, quarantaines, contrôles, limites fournisseur, checkpoints et audit.

Les schémas ci-dessus sont **des contrats cibles, pas des tables déjà créées**. Les migrations MKD sont versionnées et testées sur sa base isolée.

## Contrats de consommation — proposition

Les endpoints ci-dessous sont à implémenter et non disponibles en production.

- `GET /v1/instruments?symbol=...&mic=...&as_of=...`
- `GET /v1/bars?instrument_id=...&start=...&end=...&as_of=...`
- `GET /v1/fx?base=EUR&quote=USD&date=...&as_of=...`
- `GET /v1/quality?instrument_id=...&start=...&end=...`

Tous retournent une **erreur explicite** lorsqu'une donnée requise est absente, incohérente, non publiée à `as_of`, ou trop ancienne. Pagination et limites de volume obligatoires.

**Convention FX** : EUR/USD = USD pour 1 EUR. Un montant USD se valorise en EUR par `USD / taux_EURUSD` ; l'inverse par multiplication. Les arrondis comptables ne doivent pas être imputés aux données sources. Aucune interpolation future ; politique de taux de séance antérieure et d'âge maximal à spécifier et tester.

## W V4.2 : frontière de décision sur la structure de base

La base W actuelle contient `settings.initial_cash=500`, `orders` (sans journal d'opérations FX), `risk_stops` et `instruments.currency`. Son moteur de cash et d'equity traite **tous les prix et frais comme EUR**; les ordres USD sont explicitement refusés par `app/api/orders/route.ts` et les candidats PAPER USD sont filtrés.

**Conséquence : W V4.2 ne peut PAS activer de manière fiable les achats USD et les soldes EUR/USD séparés sans un journal durable des conversions et un traitement transactionnel multi-devises.** Ajouter des clés JSON dans `settings` ou convertir silencieusement des ordres en EUR ne résout pas l'audit comptable ni les reprises.

Découpage :
- **W V4.2-A (sans migration W)** : préparation du client MKD, lecture des cours et taux EUR/USD, calculs purs de valorisation et de sizing (read-only), tests et instrumentation de performance. **Aucun achat USD** ; aucun schéma W modifié.
- **MKD V1 prioritaire** : construire base MKD, API versionnée et FX daté, parallèlement à la correction du scanner W, puis démontrer parité sur données réelles.
- **W V4.2-B (après arbitrage explicite)** : définir et approuver une migration métier **dans la base W** pour les conversions et soldes, sauvegarde/restauration, compatibilité historique et roll-back. Ne pas la développer ou déployer avant cette approbation.

La centralisation des cours et FX **dans MKD** n'implique jamais de centraliser les portefeuilles dans MKD.

## Ordre de livraison, dépendances et recettes

1. **Inventaire** : checksum et couverture actuelle W (806 cibles EUR/USD, 779 historiques 5 ans, 23 courts, 4 rejetés, à la date 2026-11-15) ; anciens dumps conservés.
2. **Contrats MKD** : instrument, OHLCV, FX, `as_of`, erreurs, validation des sources; tests de contrats W/QE/B.
3. **PostgreSQL MKD isolé** : migrations répétables et réversibles, tests contraintes/prix/FX/horodatages.
4. **Collecte MKD** : historiques et delta quotidiens bornés, qualités et sources, reprise checkpoint, pas de prix inventés.
5. **Parité MKD↔W** : comparer OHLCV et devises sur au moins un univers et des échantillons problématiques, les 2 benchmarks, les signaux hebdomadaires et la performance. **Lecture seule du côté W**.
6. **Bascule progressive** : feature flag consommateur W, retour arrière immédiat; DB W et ordres inchangés. QE et B peuvent être branchés séparément.
7. **FX et trading USD** : contrat MKD FX validé, puis décision explicite sur la migration métier W pour ledger EUR/USD; simulation PAPER avant déploiement.

## Plan de test de non-régression

- **UT** : rejet OHLCV (high < open/close ; low > open/close), taux FX inverse, données futures, volumes invalides, symboles ambigus et splitting.
- **IT** : migrations MKD sur base jetable; ingestion idempotente; reprise sur interruption et refus fournisseur; unicité/rollback.
- **Contrats** : W, QE, B consomment les mêmes valeurs as-of et la même provenance; 404/409/422 explicites pour les cas non certifiés.
- **E2E WSL** : zéro modification des tables W; comparer 806 membres EUR/USD, les dates des benchmarks SPY/EXSA.DE, les décomptes et signaux Weinstein.
- **Risque** : confirmer que HEN3.DE reste bloqué à 500 € avec risque max 1 %, frais compris, et que tout USD reste non négociable avant l'étape W V4.2-B.
- **DRP** : sauvegarde vérifiée, restauration et contrôle de parité avant/après; échec bloquant au moindre écart inexpliqué.

## Pilotage

Trading Factory : https://github.com/users/besse79/projects/2

Dépôts et Issues de référence : MKD #1, #2, #3, #4, #5, #6, #7, #8, #9 ; W #20, #23, #25, #26. Les nouvelles US de migration et de gating doivent référencer cet ADR et leurs tests; aucune étape « réalisée » sans preuves CI et WSL.
