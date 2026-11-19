# Skills

Collection personnelle de [skills](https://docs.claude.com/en/docs/claude-code/skills) pour Claude Code et Claude.

## Skills disponibles

| Skill | Description |
|---|---|
| [`qa-test-cases`](skills/qa-test-cases/SKILL.md) | Analyse les modifications courantes d'un dépôt git et extrait, comme un analyste QA, tous les cas de tests pertinents dans un JSON structuré et validé, prêt à être transformé en collection Postman ou en scénarios Gherkin. |

## Installation

### Option 1 — Marketplace de plugins Claude Code (recommandé)

Dans Claude Code :

```
/plugin marketplace add boisvertmathieu/skills
```

```
/plugin install qa-test-cases@boisvertmathieu-skills
```

### Option 2 — Copie manuelle

Pour tous vos projets :

```bash
git clone https://github.com/boisvertmathieu/skills.git && mkdir -p ~/.claude/skills && cp -r skills/skills/qa-test-cases ~/.claude/skills/
```

Ou pour un seul projet, copiez le dossier du skill dans `.claude/skills/` à la racine du projet.

## Utilisation de `qa-test-cases`

Dans un dépôt avec des modifications en cours :

```
/qa-test-cases
```

ou en langage naturel : « Extrais les cas de tests de mes changements », « Fais l'analyse QA de ma branche par rapport à main ».

Options : `--base <ref>`, `--staged`, `--output <chemin>`, `--lang <code>`.

Le skill produit `qa-test-cases.json` (schéma : [`references/output-schema.json`](skills/qa-test-cases/references/output-schema.json), exemple : [`examples/example-output.json`](skills/qa-test-cases/examples/example-output.json)). Ensuite :

```
Génère une collection Postman à partir de qa-test-cases.json
```

```
Génère les fichiers .feature Gherkin à partir de qa-test-cases.json
```

La correspondance JSON → Postman / Gherkin est documentée dans [`references/consumer-mapping.md`](skills/qa-test-cases/references/consumer-mapping.md).

## Structure du dépôt

```
.claude-plugin/marketplace.json   # déclare chaque skill comme plugin installable
skills/
  <nom-du-skill>/
    SKILL.md                      # frontmatter (name, description) + instructions
    references/                   # documentation chargée à la demande
    scripts/                      # scripts exécutables utilisés par le skill
    examples/                     # exemples de sortie
```

## Ajouter un skill

1. Créer `skills/<nom-du-skill>/SKILL.md` avec un frontmatter `name` (identique au nom du dossier) et une `description` qui dit **quoi** et **quand** l'utiliser.
2. Ajouter une entrée dans `plugins` de `.claude-plugin/marketplace.json` (`"skills": ["./skills/<nom-du-skill>"]`).
3. Ajouter une ligne au tableau « Skills disponibles » ci-dessus.
