# Guide de conception de cas de tests (QA)

Ce guide sert de checklist pour dériver des cas de tests **pertinents** à partir d'un changement. Ne génère pas mécaniquement un cas pour chaque ligne : pour chaque comportement modifié, parcours les sections applicables et retiens les cas qui apportent une information nouvelle sur la qualité du changement.

## 1. Techniques de conception

| Technique | Quand l'utiliser | Ce qu'elle produit |
|---|---|---|
| **use-case** | Toujours, pour le chemin nominal | 1 cas par scénario d'usage principal et par variante valide significative |
| **equivalence-partitioning** | Toute entrée (champ, paramètre, en-tête, état) | 1 représentant par classe valide + 1 par classe invalide |
| **boundary-value** | Bornes numériques, longueurs, dates, tailles, quotas, pagination | min-1, min, min+1, max-1, max, max+1 ; 0, vide, 1 |
| **decision-table** | Règles métier combinant plusieurs conditions (`if a && (b \|\| c)`) | 1 cas par combinaison produisant un résultat distinct |
| **state-transition** | Statuts, workflows, cycles de vie (draft → published → archived) | Transitions valides, transitions interdites, actions répétées |
| **error-guessing** | Expérience : là où le code a typiquement des bugs | null, doublons, unicode, fuseaux horaires, arrondis, concurrence |
| **pairwise** | Beaucoup de paramètres indépendants | Couvrir chaque paire de valeurs sans explosion combinatoire |
| **risk-based** | Régression, sécurité, données | Cas ciblés sur l'impact métier le plus élevé |

Utilise `examples` dès que plusieurs cas partagent les mêmes étapes et ne diffèrent que par les données (typique des partitions et des valeurs limites).

## 2. Checklist par nature de changement

### Nouvel endpoint / nouvelle opération
- Succès nominal : code (200/201/204), corps conforme au contrat, en-têtes (`Location`, `Content-Type`).
- Persistance : relire la ressource (appel `verify`) pour prouver l'effet.
- Validation de chaque champ requis absent, null, vide, mauvais type, mauvais format, hors bornes.
- Champs inconnus / supplémentaires (rejetés ou ignorés ?).
- Authentification absente / invalide / expirée → 401.
- Autorisation : rôle insuffisant → 403 ; ressource d'un autre tenant/utilisateur → 403/404.
- Ressource parente inexistante → 404 ; doublon / conflit → 409.
- Méthode HTTP non supportée, `Content-Type` incorrect → 405/415.
- Pagination, tri, filtres : première/dernière page, page vide, taille max, paramètres invalides.

### Endpoint ou comportement existant modifié
- Le **nouveau** comportement, sur le chemin nominal et ses variantes.
- L'**ancien** comportement qui doit être préservé pour les cas non visés (non-régression).
- **Rétrocompatibilité** du contrat : champ renommé/supprimé, type changé, nouvelle valeur d'enum, champ devenu obligatoire, valeur par défaut modifiée, code HTTP changé.
- Clients existants qui envoient l'ancien format.

### Correction de bug
- Un cas qui **reproduit exactement le bug** (doit maintenant passer) — priorité P1, tag `@bugfix`.
- Les variantes proches du scénario du bug (mêmes conditions avec une donnée voisine).
- La non-régression du comportement correct autour du correctif.

### Règle métier / calcul
- Table de décision complète des conditions.
- Valeurs limites de chaque seuil (ex. remise à partir de 100 $ : 99.99, 100.00, 100.01).
- Arrondis, devises, précision décimale, valeurs négatives, zéro.
- Dates : fin de mois, année bissextile, fuseaux horaires, changement d'heure, dates passées/futures.

### Machine à états / workflow
- Chaque transition autorisée et son résultat (statut, horodatage, événement émis).
- Chaque transition interdite → erreur explicite, état inchangé.
- Répéter la même action (idempotence) ; actions concurrentes sur la même ressource.

### Validation / formats d'entrée
- Chaînes : vide, espaces seuls, longueur max/max+1, unicode/emoji, caractères spéciaux, HTML/script.
- Nombres : 0, négatif, décimal quand entier attendu, très grand, notation scientifique, chaîne numérique.
- Formats : email, URL, UUID, date ISO, téléphone — valides et invalides.
- Collections : vide, 1 élément, nombre max, doublons.

### Sécurité
- Injection (SQL/NoSQL/commande/LDAP) dans les champs nouveaux ou modifiés.
- XSS stocké/réfléchi si la donnée est réaffichée.
- IDOR : accéder/modifier la ressource d'un autre utilisateur en changeant l'identifiant.
- Escalade de privilèges : champ `role`, `isAdmin`, `ownerId` envoyé par le client (mass assignment).
- Données sensibles absentes de la réponse (mot de passe, hash, token, PII) et des logs.
- Rate limiting, taille de payload maximale, upload de fichier (type, taille, nom malicieux).

### Données / migration de schéma
- Données existantes créées avant le changement : toujours lisibles et correctes.
- Valeurs par défaut appliquées aux lignes existantes.
- Migration ré-exécutable / rollback si prévu.
- Contraintes (unicité, non-null, clé étrangère) appliquées par l'API avec une erreur claire.

### Intégrations / dépendances externes
- Dépendance indisponible, lente (timeout), réponse invalide → comportement dégradé attendu, message d'erreur, retry.
- Événements/messages publiés : contenu, unicité, ordre ; consommation d'un message dupliqué.

### Configuration / feature flag
- Flag activé et flag désactivé (l'ancien comportement doit rester intact quand désactivé).
- Valeur de configuration absente ou invalide.

### Refactor (sans changement fonctionnel attendu)
- Surtout des cas `regression` couvrant les comportements observables du code touché : chemin nominal, erreurs principales, cas limites déjà connus.
- Marque les comportements avec `kind: "unchanged-regression-risk"`.

### UI
- Affichage des états : chargement, vide, erreur, succès.
- Validation côté client cohérente avec le serveur.
- Navigation, rafraîchissement, bouton retour, double-clic sur soumission.
- Accessibilité (clavier, libellés, contraste) si les composants changent.
- Utilise `level: "ui"` ou `"e2e"` et omets `api` si le cas n'est pas exécutable par API.

### Performance / concurrence (seulement si le changement y touche)
- Requêtes N+1, gros volumes, pagination sur grande collection.
- Deux requêtes simultanées sur la même ressource (conditions de course, verrouillage optimiste).

## 3. Priorisation

| Priorité | Critère |
|---|---|
| **P1** | Cœur du changement (chemin nominal), reproduction d'un bug corrigé, sécurité/autorisation, perte ou corruption de données, rupture de contrat |
| **P2** | Validations importantes, erreurs fréquentes, variantes métier, non-régression proche |
| **P3** | Cas marginaux, cosmétiques, combinaisons rares |

`severityIfFails` décrit l'impact en production si le cas échoue (indépendant de la probabilité).

## 4. Tags recommandés

`@smoke` (sous-ensemble minimal P1 à exécuter en premier), `@regression`, `@negative`, `@security`, `@bugfix`, `@boundary`, `@contract`, `@data-migration`, plus un tag par feature (ex. `@orders`). Les tags deviennent des tags Gherkin et peuvent servir à filtrer les dossiers Postman.

## 5. Anti-patterns à éviter

- Cas sans résultat attendu vérifiable (« vérifier que ça marche »).
- Endpoints, champs, messages ou codes inventés : vérifie dans le code ; sinon variable + question ouverte.
- Un cas qui teste dix choses : découpe-le.
- Dupliquer un cas pour chaque valeur au lieu d'utiliser `examples`.
- Ignorer la non-régression parce que « seul le nouveau code compte ».
- Tester des détails d'implémentation internes (nom de fonction privée) au lieu du comportement observable.
- Étapes Gherkin techniques (« le JSON contient `$.data[0].id` ») : garde les détails techniques dans `api`, et un langage métier dans `gherkin`.
