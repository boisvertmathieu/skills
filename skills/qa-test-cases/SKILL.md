---
name: qa-test-cases
description: Analyse les modifications courantes d'un dépôt git (working tree, index, ou branche vs base) et en extrait, comme le ferait un analyste QA, tous les cas de tests pertinents couvrant la nature complète du changement (fonctionnels, négatifs, limites, sécurité, régression, etc.). Produit un fichier JSON structuré et validé, conçu pour être réutilisé par un agent afin de générer une collection Postman ou des scénarios Gherkin. Utiliser quand l'utilisateur demande des cas de tests, un plan de tests, une analyse QA, des scénarios de test ou des tests d'acceptation à partir d'un diff, d'une PR, d'une branche ou de « mes changements » — aussi en anglais (test cases from diff, QA analysis, test plan, Postman, Gherkin, BDD scenarios).
---

# Extraction de cas de tests QA à partir des modifications d'un dépôt

Tu joues le rôle d'un **analyste QA senior**. Ton objectif n'est pas de tester des lignes de code, mais de tester **la nature du changement dans son ensemble** : ce que le changement est censé faire, ce qu'il ne doit pas casser, et tout ce qui peut mal tourner autour.

Le livrable est un **fichier JSON conforme à `references/output-schema.json`**, réutilisable tel quel par un autre agent pour produire une collection Postman ou des fichiers `.feature` Gherkin. La qualité du JSON (complétude, cohérence des références, précision des assertions) est aussi importante que la qualité des cas de tests.

## Arguments acceptés (optionnels)

- `--base <ref>` : compare la branche courante (plus les changements non commités) à `<ref>` (ex. `main`, `origin/develop`).
- `--staged` : seulement les changements indexés.
- `--output <chemin>` : chemin du fichier JSON produit (défaut : `qa-test-cases.json` à la racine du dépôt).
- `--lang <code>` : langue des textes (défaut : langue de l'utilisateur). Les **clés JSON et valeurs d'énumération restent toujours en anglais**.
- Un focus libre (ex. « seulement l'API », « niveau UI ») : respecte-le et note-le dans `changeSummary.outOfScope`.

## Workflow

### 1. Collecter les modifications

Exécute le script de collecte depuis la racine du dépôt analysé :

```bash
bash <chemin-du-skill>/scripts/collect_changes.sh [--base <ref>] [--staged]
```

Sans argument, il détecte automatiquement la portée : changements non commités s'il y en a, sinon commits de la branche courante non présents dans la branche par défaut. Il affiche les métadonnées (dépôt, branche, commit, portée), la liste des fichiers modifiés, les statistiques, le diff complet et les fichiers non suivis.

Si le diff est vide, arrête-toi et dis-le à l'utilisateur (propose `--base`).

### 2. Comprendre le changement (ne te limite pas au diff)

Un hunk isolé ment souvent. Pour chaque fichier significatif :

- **Lis le fichier complet** (et pas seulement les lignes modifiées) pour comprendre le contexte.
- **Remonte aux points d'entrée** : routes/contrôleurs, résolveurs GraphQL, handlers d'événements, commandes CLI, jobs planifiés, composants UI. Cherche les appelants des fonctions modifiées (`grep`).
- **Identifie les contrats** : DTO, schémas de validation, modèles, migrations, OpenAPI/Swagger, types, messages d'erreur, codes HTTP, permissions/rôles, feature flags, configuration.
- **Lis les tests existants** liés au code modifié : ils révèlent l'intention et les cas déjà couverts.
- **Lis les messages de commit** et, si disponible, la description de PR ou le ticket mentionné.

Puis formule pour toi-même :
- **L'intention** du changement (feature, bugfix, refactor, perf, sécurité, config, migration…).
- **Les comportements modifiés** : pour chacun, le comportement *avant* et *après*. Un refactor sans changement de comportement produit surtout des tests de **non-régression**.
- **Les surfaces impactées indirectement** (code appelant, données existantes, clients de l'API, autres services).
- **Les hypothèses** que tu fais et les **questions ouvertes** (ambiguïtés de spécification) : ne les invente pas en silence, consigne-les.

### 3. Concevoir les cas de tests

Applique systématiquement les techniques et la checklist de `references/test-design-guide.md`. Pour chaque comportement modifié, pose-toi au minimum ces questions :

1. **Chemin nominal** : le changement fait-il ce qu'il doit faire, pour chaque variante valide significative ?
2. **Partitions d'équivalence et valeurs limites** sur chaque entrée nouvelle ou modifiée (min, min-1, max, max+1, vide, null, absent, type invalide, format invalide, unicode, très long).
3. **Règles métier / tables de décision** : chaque combinaison de conditions pertinente.
4. **Transitions d'état** : transitions valides, transitions interdites, répétition (idempotence).
5. **Erreurs et cas négatifs** : dépendances en échec, ressource inexistante, conflit, timeouts, messages et codes d'erreur exacts.
6. **Sécurité et autorisations** : non authentifié, mauvais rôle, accès à la ressource d'un autre utilisateur (IDOR), injection, exposition de données sensibles dans la réponse ou les logs.
7. **Non-régression** : quels comportements existants proches pourraient être cassés ? Rétrocompatibilité des contrats (champ renommé/retiré, valeur par défaut changée).
8. **Données et migrations** : données existantes avant le changement, migration aller/retour, valeurs par défaut.
9. **Concurrence, performance, i18n, accessibilité** : seulement si le changement y touche réellement.

Règles de qualité :
- **Un cas = un objectif vérifiable**. Pas de cas fourre-tout. Utilise `examples` (data-driven) plutôt que de dupliquer des cas qui ne diffèrent que par les données.
- **Pertinence avant exhaustivité aveugle** : chaque cas doit être traçable à un comportement modifié (`coversBehaviors`) ou à un risque de régression explicite. N'invente pas d'endpoints, de champs ou de règles absents du code ; si une information manque, utilise une variable (`{{...}}`) et ajoute une question ouverte.
- **Résultats attendus précis et observables** : code HTTP exact, champs et valeurs attendus, message d'erreur, effet de bord (ligne en BD, événement publié, email envoyé). Évite « ça fonctionne ».
- **Priorise par risque** : `P1` = cœur du changement / perte de données / sécurité ; `P2` = variantes et erreurs importantes ; `P3` = cas marginaux.
- **Indépendance** : chaque cas déclare ses préconditions, ses appels de setup et de nettoyage. Utilise `dependsOn` seulement si inévitable.

### 4. Construire le JSON

Lis `references/output-schema.json` (schéma JSON faisant foi) et `references/consumer-mapping.md` (comment un agent consommateur transformera ta sortie en Postman / Gherkin — écris en conséquence). Un exemple complet se trouve dans `examples/example-output.json`.

Points essentiels :
- `features[]` regroupe les cas par fonctionnalité/capacité impactée (→ un `Feature:` Gherkin, un dossier Postman).
- `features[].changedBehaviors[]` décrit chaque comportement avant/après avec ses `sourceRefs` (fichier + lignes).
- `features[].interfaces[]` décrit les points d'entrée (endpoint HTTP, mutation GraphQL, page UI, événement…).
- Chaque `testCase` contient **toujours** un bloc `gherkin` (given/when/then en langage naturel, orienté métier, sans détail technique superflu) et, **quand le cas est exécutable via une API**, un bloc `api.calls[]` ordonné (setup → action → verify → cleanup) avec requêtes complètes, assertions et extraction de variables.
- Placeholders : `{{variable}}` dans `api` (syntaxe Postman), `<parametre>` dans `gherkin` (syntaxe Scenario Outline). Les clés de `examples[].values` correspondent aux deux.
- Toute variable utilisée doit être déclarée dans `context.variables`, extraite par un `extract` précédent, ou fournie par `examples`.
- IDs stables et lisibles : `F1`, `B1.1`, `I1.1`, `TC-F1-001`, `td-...`, `auth-...`.

### 5. Valider

```bash
python3 <chemin-du-skill>/scripts/validate_output.py <fichier.json>
```

Le validateur vérifie la structure, les énumérations, l'unicité des IDs, l'intégrité référentielle (behaviors, interfaces, auth, données de test, dépendances, variables) et la couverture de chaque comportement. **Corrige toutes les erreurs** et examine les avertissements avant de livrer. Itère jusqu'à obtenir `OK`.

### 6. Livrer

- Écris le fichier JSON (ne le commite pas sauf demande explicite).
- Réponds à l'utilisateur avec un résumé court :
  - intention du changement et niveau de risque ;
  - nombre de cas par feature, par priorité et par type ;
  - les questions ouvertes / hypothèses importantes ;
  - les zones non couvertes ou hors portée ;
  - le chemin du fichier et la suggestion de l'étape suivante (ex. « demande-moi de générer la collection Postman ou les fichiers .feature à partir de ce fichier »).

Si l'utilisateur demande directement la collection Postman ou les scénarios Gherkin, produis d'abord ce JSON, valide-le, puis applique `references/consumer-mapping.md`.
