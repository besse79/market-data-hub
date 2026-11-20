# Recette WSL — Trading Factory — 21 novembre 2026

## Objet
Préparer une recette non destructive de MarketDataHub (MKD), Weinstein'S (W), QuantEdge (QE) et BuffettValue (B). Ce document ne vaut ni preuve d'exécution WSL ni autorisation de bascule.

## Préconditions et interdictions
- Aucun ordre réel. PAPER uniquement, portefeuille initial de 500 EUR par moteur.
- Ne jamais exécuter de DDL/DML sur la base W existante. Ne pas migrer la structure W.
- Avant toute écriture MKD : sauvegarde PostgreSQL MKD datée, empreinte SHA256, test de restauration dans une base isolée.
- Inventorier et photographier la base W en lecture seule (schéma, volumes, positions, ordres, stops, hash/export).
- Ne pas inventer de timestamps de publication historiques : marquer les historiques importés `legacy_unverified`, exclus des backtests point-in-time.
- Si une source, un FX, un benchmark ou une bougie est périmé ou incohérent : blocage explicite, pas de fallback silencieux.

## Étape 1 — Audit en lecture seule
- Identifier les branches/commits réellement déployés dans les 4 repos et MKD.
- Relever les PR non fusionnées, CI, variables d'environnement (sans afficher les secrets), ports et volumes Docker.
- Contrôler la fraîcheur EOD (date dernière bougie) pour SPY, EXSA.DE, échantillons EUR et USD.
- Capturer les comptages source W : référence documentée 1 107 instruments, 840 avec OHLCV, 267 sans bougies, 1 041 814 bougies ; comparer aux comptages réels, sans supposer leur exactitude aujourd'hui.

## Étape 2 — MKD : tests et service
- Installer les dépendances dans un environnement isolé ; exécuter `python -m pytest` et `alembic upgrade head` uniquement sur base MKD de test.
- Vérifier PostgreSQL isolé ; noter que le compose de `feature/v1-foundation` ne contient qu'un service postgres, donc valider le lancement FastAPI séparément.
- Vérifier liveness, `GET /v1/instruments`, `GET /v1/bars`, `GET /v1/fx` avec données réelles et cas d'erreur.
- Vérifier BIGINT pour les volumes > 2^31, dates futures, doublons, devises et OHLCV invalides.
- Vérifier provenance, `as_of`, qualité et absence d'utilisation PIT des lignes `legacy_unverified`.

## Étape 3 — Import historique non destructif
- Dry-run depuis copie isolée de W ; manifeste des instruments avec MIC, classe, devise.
- Contrôler le rapport des rejets (notamment CPG.L, IHG.L, VSURE.ST si toujours ambigus).
- Importer dans MKD isolé seulement après sauvegarde/restauration vérifiée.
- Tester idempotence, reprise sur interruption, parité OHLCV par instrument/date, nombre de bougies et empreintes.
- Vérifier absence d'écriture sur W et restaurabilité MKD.

## Étape 4 — Connexion W / MKD
- Tester l'adaptateur W V4.2-A en lecture seule, flag OFF par défaut.
- Vérifier que le scanner opérationnel W reste sur sa base locale avant GO.
- Comparer MM30, phases, volumes, supports, signaux et benchmarks sur mêmes dates.
- Rejeter toute exécution PAPER USD tant que FX et ledger USD ne sont pas validés.
- Vérifier UI, API, journal de blocage, collecte quotidienne et rollback.

## Étape 5 — QE et B
- QE : momentum, volatilité, liquidité, classement, backtest walk-forward, frais/slippage, absence de lookahead, portefeuille PAPER 500 EUR.
- B : états financiers SEC datés, revisions, DCF et sensibilité, marge de sécurité, devise, absence de lookahead, portefeuille PAPER 500 EUR.
- Ne pas déclarer opérationnels les moteurs dont la collecte ou les tests E2E restent manquants.

## Étape 6 — Banc d'essai
- Même calendrier, mêmes données de référence, coûts et FX documentés.
- Produire chaque jour : date as-of, version code/données, signaux, ordres fictifs, exécutions simulées, frais, positions, cash, equity, drawdown, blocages.
- Benchmarks MSCI World / S&P 500 : sources et dates de publication vérifiées.
- Aucun achat si données essentielles manquantes.

## Livrables de recette
1. `audit-versions.md` : SHA, branche, CI, statut des PR.
2. `mkd-data-parity.csv` : écarts par symbole/date/OHLCV.
3. `quality-gates.json` : chaque contrôle GO/NO-GO avec preuve.
4. `wsl-test-results.md` : commandes, sorties, erreurs, correctifs.
5. `paper-daily-report.csv` : premier cycle simulé de chaque moteur.

## GO/NO-GO
GO MKD : service API accessible + données réelles certifiées + import/parité validés + rollback testé.
GO W : MKD GO si dépendance activée + E2E PAPER + absence de régression W + aucun ordre USD non autorisé.
GO QE/B : sources PIT disponibles + backtest sans anticipation + PAPER E2E + CI et WSL réussis.
