# Guide de consommation de la sortie (Postman / Gherkin)

Ce document décrit comment un agent transforme le JSON produit par le skill `qa-test-cases` en artefacts exécutables. Le producteur doit le lire pour écrire un JSON directement exploitable ; le consommateur l'applique tel quel.

## 1. Vers une collection Postman (format v2.1.0)

### Structure

| JSON qa-test-cases | Postman |
|---|---|
| racine | `info.name` = `changeSummary.title`, `info.description` = `changeSummary.description` + hypothèses + questions ouvertes, `info.schema` = `https://schema.getpostman.com/json/collection/v2.1.0/collection.json` |
| `context.variables[]` | `variable[]` de la collection (`key`=`name`, `value`=`example`, `description`). Les `secret: true` gardent une valeur vide et sont listées dans la description (à mettre dans un environnement) |
| `context.auth[]` | Appliqué par requête via `api.calls[].auth` (voir ci-dessous) |
| `features[]` | Un dossier (`item` avec sous-`item`) par feature : `name` = `"{id} - {name}"`, `description` = description + userStory |
| `features[].testCases[]` | Un sous-dossier par cas : `name` = `"{id} - {title}"`, `description` = objective, préconditions, expectedResult, sideEffects, tags, priorité |
| `testCases[].api.calls[]` | Une requête par appel, dans l'ordre, `name` = `"[{role}] {name}"` |
| Cas sans `api` | Ne pas créer de requête ; lister le cas dans la description du dossier de feature sous « Cas manuels / UI » |

Un dossier par cas garantit l'isolation (setup → action → verify → cleanup) et permet l'exécution d'un cas seul dans le Collection Runner.

### Requête

- `request.method` = `method`
- `request.url.raw` = `url` + query string construite à partir de `query` ; renseigner aussi `url.query[]` (`key`, `value`).
- `request.header[]` à partir de `headers` (+ `Content-Type` = `body.contentType` si absent).
- `body` :
  - `json` → `mode: "raw"`, `raw: JSON.stringify(content, null, 2)`, `options.raw.language: "json"`
  - `raw` → `mode: "raw"`, `raw: content`
  - `urlencoded` / `formdata` → `mode` identique, tableau `{key, value}`
  - `graphql` → `mode: "graphql"`, `graphql: {query, variables}`
  - `none` ou absent → pas de body
- `auth` : résoudre `context.auth[id]` :
  - `bearer` → `{type:"bearer", bearer:[{key:"token", value: config.token}]}`
  - `basic` → `{type:"basic", basic:[{key:"username",...},{key:"password",...}]}`
  - `apiKey` → `{type:"apikey", apikey:[{key:"key",value:config.key},{key:"value",value:config.value},{key:"in",value:config.in}]}`
  - `none` → `{type:"noauth"}` (important pour les cas « non authentifié » : empêche l'héritage)
  - `cookie` / `custom` → en-têtes explicites selon `config`

### Tests (script `test` de chaque requête)

Générer un `event` `listen: "test"` avec :

```js
// expect.status
pm.test("Status is 201", () => pm.response.to.have.status(201));
// liste de codes acceptables
pm.test("Status is one of [200,204]", () => pm.expect(pm.response.code).to.be.oneOf([200, 204]));
// maxResponseTimeMs
pm.test("Response time < 800ms", () => pm.expect(pm.response.responseTime).to.be.below(800));
```

Pour les assertions `target: "body"`, résoudre le JSONPath avec un petit helper inclus une fois au niveau de la collection (script `prerequest` ou `test` de collection, exposé via `pm.globals`/fonction locale) ou, plus simplement, convertir les chemins simples (`$.a.b[0].c`) en accès JavaScript (`json.a.b[0].c`) :

| operator | Snippet (`v` = valeur résolue, `x` = `value`) |
|---|---|
| equals / notEquals | `pm.expect(v).to.eql(x)` / `.to.not.eql(x)` |
| exists / notExists | `pm.expect(v).to.not.be.undefined` / `.to.be.undefined` |
| contains / notContains | `pm.expect(v).to.include(x)` / `.to.not.include(x)` |
| matches | `pm.expect(v).to.match(new RegExp(x))` |
| gt / gte / lt / lte | `.to.be.above(x)` / `.at.least(x)` / `.below(x)` / `.at.most(x)` |
| isType | `pm.expect(v).to.be.a(x)` (`array` → `.to.be.an('array')`, `null` → `.to.be.null`) |
| lengthEquals / lengthGte / lengthLte | `.to.have.lengthOf(x)` / `.length.at.least(x)` / `.length.at.most(x)` |
| oneOf | `pm.expect(v).to.be.oneOf(x)` |
| isEmpty / isNotEmpty | `.to.be.empty` / `.to.not.be.empty` |
| matchesSchema (`target: "schema"`) | `pm.response.to.have.jsonSchema(x)` |

- `target: "header"` → `pm.response.headers.get(path)` ; `target: "cookie"` → `pm.cookies.get(path)`.
- Utiliser `description` de l'assertion comme libellé du `pm.test` quand présente.

### Variables extraites

```js
// extract: {variable: "orderId", from: "body", path: "$.id"}
pm.collectionVariables.set("orderId", pm.response.json().id);
// from: header
pm.collectionVariables.set("location", pm.response.headers.get("Location"));
```

### Données d'exemple (`examples`)

Postman n'exécute pas d'itérations par dossier. Deux options, au choix du consommateur :
1. **Fichier de données** (recommandé pour le Runner/Newman) : produire un CSV/JSON par cas, `testCaseId.data.json` = tableau des `values`, à passer via `newman run -d`. Documenter la commande dans la description du dossier.
2. **Dépliage** : dupliquer le dossier du cas pour chaque exemple (`"{id} - {title} [{example.name}]"`) en remplaçant les `{{clé}}` par les valeurs. À privilégier pour une collection autonome.

Les clés de `examples[].values` peuvent aussi apparaître dans `expect` (ex. `"status": "{{expectedStatus}}"`) : les remplacer de la même façon (ou lire `pm.iterationData.get("expectedStatus")` en mode fichier de données).

### Préconditions et données de test

- `features[].background.given` et `testCases[].preconditions` → texte dans la description.
- `context.testData[].setup` → si c'est un appel API décrit, il doit déjà figurer comme `call` de rôle `setup` ; sinon le mentionner dans la description (étape manuelle/seed).

## 2. Vers des scénarios Gherkin (`.feature`)

### Structure

- Un fichier par feature : `features/{id}-{slug(name)}.feature`.
- En-tête de langue si la langue n'est pas l'anglais : `# language: fr` (mots-clés `Fonctionnalité`, `Contexte`, `Scénario`, `Plan du scénario`, `Exemples`, `Soit`/`Étant donné`, `Quand`, `Alors`, `Et`, `Mais`).

| JSON | Gherkin |
|---|---|
| `features[].tags` | tags au-dessus de `Feature:` |
| `features[].name` | `Feature: {name}` |
| `features[].userStory` / `description` | texte libre sous `Feature:` |
| `features[].background.given` | `Background:` avec `Given` / `And` |
| `testCases[]` | `Scenario:` (ou `Scenario Outline:` si `examples` non vide) |
| `testCases[].tags` + `@{id}` + `@{priority}` | tags au-dessus du scénario (ex. `@TC-F1-001 @P1 @smoke`) |
| `gherkin.given[0]`, `given[1..]` | `Given …`, puis `And …` |
| `gherkin.when[0]`, `when[1..]` | `When …`, puis `And …` |
| `gherkin.then[0]`, `then[1..]` | `Then …`, puis `And …` |
| `examples[]` | `Examples:` table ; colonnes = clés de `values` (+ colonne `name` en premier si utile) |

Les placeholders `<param>` des étapes correspondent aux colonnes de la table `Examples`.

### Exemple

```gherkin
# language: fr
@orders
Fonctionnalité: Création de commande avec code promo
  En tant que client, je veux appliquer un code promo afin d'obtenir une remise.

  Contexte:
    Soit un client authentifié avec un panier contenant des articles

  @TC-F1-002 @P1 @boundary
  Plan du scénario: Application de la remise selon le montant du panier
    Soit un panier d'un montant de <montant> $
    Quand le client valide la commande avec le code "PROMO10"
    Alors la remise appliquée est de <remise> $

    Exemples:
      | montant | remise |
      | 99.99   | 0.00   |
      | 100.00  | 10.00  |
```

### Step definitions (optionnel)

Si le consommateur génère aussi les step definitions, il peut s'appuyer sur `api.calls[]` du même cas : les étapes `Given` ↔ appels `setup`, `When` ↔ appels `action`, `Then` ↔ `expect` des appels `action` et appels `verify`.
