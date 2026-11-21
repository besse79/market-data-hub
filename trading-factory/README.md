# Trading Factory — agent local WSL

Ce dépôt contient le bootstrap de l'agent de recette **sans privilèges root**. GitHub Project V2 : https://github.com/users/besse79/projects/2

## Démarrage (WSL Ubuntu)
Exécuter `bash trading-factory/install-local-agent.sh` après avoir récupéré cette branche. Le script ne modifie pas les bases de données et ne démarre aucun trading.

Le bootstrap vérifie git, gh, python3, node, npm et docker, initialise un espace isolé et prépare une tâche locale de diagnostic. Il **n'installe pas silencieusement** un runner GitHub ni Codex : l'enregistrement du runner nécessite un jeton éphémère et un choix explicite de droits, et Codex nécessite une authentification propre.

## Synchronisation GitHub
Le rapport local est un fichier JSON sous `~/trading-factory-agent/reports/`. Une intégration GitHub Project V2 exige un jeton avec permission **Projects** (distinct des droits dépôt). Les issues restent la source de vérité des tâches, les PR de la livraison et les résultats CI de la recette.

## Sécurité
Ne pas exécuter de PR externes sur un runner qui accède à PostgreSQL ou aux identifiants locaux. Ne pas activer `pull_request_target` ni exposer de secrets aux jobs non fiables. Les déploiements Hippique requièrent sauvegarde, contrôle d'intégrité et restauration. PAPER et PIT restent NO-GO tant que les données ne sont pas certifiées.

## Cycle
Issue priorisée -> branche dédiée -> développement -> tests -> PR -> recette -> clôture. Une PR créée ou une CI verte ne ferme pas seule une US. Les changements destructifs, trading réel et paris réels exigent une approbation humaine.
