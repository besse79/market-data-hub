# Synchronisation GitHub Project V2

Projet: https://github.com/users/besse79/projects/2

## Schéma de gestion
- Epic: objectif produit transverse
- Feature: capacité livrable
- User Story: besoin et critères d'acceptation
- Task: travail technique exécutable
- Bug: défaut reproductible et gravité
- Test: protocole et preuve de recette

Champs recommandés: Product (MKD/W/QuantEdge/BuffettValue/Hippique), Type, Priority (P0/P1/P2), Status (Backlog/Ready/In Progress/In Review/In Test/Blocked/Done), Owner, Iteration, Evidence URL, Blocker, Decision.

## Automates
- Issue marquée Ready + approuvée -> éligible à la file d'exécution
- Début effectif -> In Progress
- PR créée -> In Review
- Tests réussis -> In Test (jamais Done directement)
- Tests échoués -> Bug lié, statut Blocked si bloquant
- PR fusionnée ET critères d'acceptation validés -> Done
- Rapport quotidien -> résumé par produit, incidents, décisions et 3 priorités

## Accès
GitHub Apps de dépôt et GitHub Projects V2 possèdent des autorisations distinctes. Ne pas annoncer une synchronisation active avant d'avoir vérifié les permissions Projects et réalisé un test de mise à jour de champ.

## Contrôles
- Un identifiant de ticket stable dans les branches/PR/logs.
- Idempotence: aucune duplication de Bug à chaque échec.
- Aucune clôture automatique sur seul statut CI.
- Journal d'audit des changements d'état.
- Pas de secrets ni données de production dans les artefacts publics.
