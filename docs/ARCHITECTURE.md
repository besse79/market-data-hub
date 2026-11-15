# MarketDataHub — architecture V1

## Rôle
Service indépendant de collecte et distribution de données de marché pour Weinstein'S, QuantEdge et BuffettValue. Aucune décision de trading dans ce dépôt.

## Périmètre V1
- Référentiel instruments avec identifiants persistants, places de cotation, devises, statuts de cotation.
- Prix quotidiens OHLCV, prix ajustés, dividendes, splits, indices et FX.
- Provenance, date de collecte, version du fournisseur, contrôles qualité, journal des anomalies.
- Univers datés (composition historique) pour limiter le biais de survivance.
- API FastAPI versionnée, accès lecture seule pour consommateurs.
- PostgreSQL central, migrations, sauvegardes, export d'instantanés cohérents.

## V2 fondamentale
- SEC EDGAR: états financiers et données XBRL, dates de dépôt et disponibilité effective.
- Ratios dérivés calculés à partir de données datées, sans utiliser d'informations futures.
- Extension Euronext après vérification des sources et de leurs licences.

## Invariants
- Pas d'altération silencieuse des historiques.
- Pas d'ordre ni de portefeuille dans le hub.
- Données absentes, incohérentes ou périmées signalées explicitement.
- Pas de migration automatique des bases Weinstein'S.
- Tests de parité avant toute bascule des consommateurs.
- Respect des licences et conditions d'utilisation des sources gratuites.

## Séquence de réalisation
1. Auditer les schémas et collecteurs existants, sans modifier les dépôts sources.
2. Définir le schéma versionné et les contrats d'API.
3. Implémenter collecte incrémentale idempotente et validation.
4. Tester les exports, sauvegardes et reprise après erreur.
5. Brancher QuantEdge, puis BuffettValue, puis Weinstein'S après validation.
