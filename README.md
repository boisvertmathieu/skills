# Skills

Collection personnelle de skills pour agents IA. Les skills suivent le format ouvert **Agent Skills** (un dossier contenant un `SKILL.md` avec un frontmatter `name` / `description`, accompagné de références et de scripts) et ne dépendent d'aucun agent, IDE ou modèle en particulier.

## Skills disponibles

| Skill | Description |
|---|---|
| [`qa-test-cases`](skills/qa-test-cases/SKILL.md) | Analyse les modifications courantes d'un dépôt git et extrait, comme un analyste QA, tous les cas de tests pertinents dans un JSON structuré et validé, prêt à être transformé en collection Postman ou en scénarios Gherkin. |

## Installation

### Agents qui prennent en charge les skills

Copiez le dossier du skill dans le répertoire de skills de votre agent :

```bash
git clone https://github.com/boisvertmathieu/skills.git
```

```bash
cp -r skills/skills/qa-test-cases <REPERTOIRE_DE_SKILLS_DE_VOTRE_AGENT>/
```

Exemples de répertoires (ils évoluent : vérifiez la documentation de votre agent) :

| Agent | Personnel | Par projet |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| OpenAI Codex | `~/.codex/skills/` | — |

### Agents sans prise en charge native

Le `SKILL.md` est un simple fichier Markdown d'instructions. Vous pouvez :
- le référencer depuis le fichier d'instructions de votre agent (ex. `AGENTS.md`) : « Pour extraire des cas de tests, suis `skills/qa-test-cases/SKILL.md` » ;
- ou le fournir directement comme instructions ou prompt, avec le dossier du skill accessible pour les scripts et références.

### Intégrations optionnelles

Le fichier `.claude-plugin/marketplace.json` permet aussi d'installer les skills comme plugins dans Claude Code (`/plugin marketplace add boisvertmathieu/skills`). Il ne sert qu'à cette intégration : les skills eux-mêmes n'en dépendent pas.

## Utilisation de `qa-test-cases`

Dans un dépôt avec des modifications en cours, demandez à votre agent par exemple :

- « Extrais les cas de tests de mes changements »
- « Fais l'analyse QA de ma branche par rapport à `main` »

Options possibles dans la demande : base de comparaison, index seulement, chemin de sortie, langue, focus (API, UI…).

Le skill produit `qa-test-cases.json` (schéma : [`references/output-schema.json`](skills/qa-test-cases/references/output-schema.json), exemple : [`examples/example-output.json`](skills/qa-test-cases/examples/example-output.json)). Ensuite :

- « Génère une collection Postman à partir de `qa-test-cases.json` »
- « Génère les fichiers `.feature` Gherkin à partir de `qa-test-cases.json` »

La correspondance JSON → Postman / Gherkin est documentée dans [`references/consumer-mapping.md`](skills/qa-test-cases/references/consumer-mapping.md).

Prérequis des scripts : `git`, `bash`, `python3` (bibliothèque standard uniquement).

## Structure du dépôt

```
skills/
  <nom-du-skill>/
    SKILL.md                      # frontmatter (name, description) + instructions
    references/                   # documentation chargée à la demande
    scripts/                      # scripts exécutables utilisés par le skill
    examples/                     # exemples de sortie
.claude-plugin/marketplace.json   # optionnel : intégration plugin Claude Code
```

## Ajouter un skill

1. Créer `skills/<nom-du-skill>/SKILL.md` avec un frontmatter `name` (identique au nom du dossier, en minuscules et tirets) et une `description` qui dit **quoi** faire et **quand** l'utiliser.
2. Rester agnostique : pas d'outils, de commandes ou de chemins propres à un agent dans les instructions. Les scripts doivent utiliser des outils standards, et les chemins être relatifs au dossier du skill.
3. Ajouter une ligne au tableau « Skills disponibles » ci-dessus.
4. Optionnel : ajouter une entrée dans `plugins` de `.claude-plugin/marketplace.json`.
