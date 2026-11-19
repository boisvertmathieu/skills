#!/usr/bin/env python3
"""Valide un fichier produit par le skill qa-test-cases.

Usage : python3 validate_output.py <fichier.json> [--schema <output-schema.json>] [--strict]

Vérifie :
  1. la conformité au JSON Schema (sous-ensemble implémenté sans dépendance externe) ;
  2. l'unicité des identifiants ;
  3. l'intégrité référentielle (behaviors, interfaces, auth, acteurs, données de test,
     dépendances, variables {{...}}, placeholders <...> et examples) ;
  4. la couverture (chaque comportement modifié couvert par au moins un cas).

Code de sortie : 0 si aucune erreur (avertissements permis, sauf avec --strict), 1 sinon.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "references" / "output-schema.json"
VAR_RE = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
PLACEHOLDER_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_\-]*)>")


# --------------------------------------------------------------------------- #
# Mini validateur JSON Schema (sous-ensemble utilisé par output-schema.json)   #
# --------------------------------------------------------------------------- #
TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaValidator:
    def __init__(self, root: dict):
        self.root = root

    def resolve(self, ref: str) -> dict:
        if not ref.startswith("#/"):
            raise ValueError(f"$ref non supportée : {ref}")
        node = self.root
        for part in ref[2:].split("/"):
            node = node[part]
        return node

    def validate(self, value, schema: dict, path: str = "$") -> list[str]:
        errors: list[str] = []
        if "$ref" in schema:
            return self.validate(value, self.resolve(schema["$ref"]), path)

        if "const" in schema and value != schema["const"]:
            errors.append(f"{path} : doit valoir {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{path} : {value!r} n'est pas parmi {schema['enum']}")

        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(TYPE_CHECKS[t](value) for t in types):
                errors.append(f"{path} : type attendu {'|'.join(types)}, obtenu {type(value).__name__}")
                return errors

        if "oneOf" in schema:
            matches = [s for s in schema["oneOf"] if not self.validate(value, s, path)]
            if len(matches) != 1:
                errors.append(f"{path} : doit correspondre à exactement une des formes permises")

        if isinstance(value, str):
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errors.append(f"{path} : {value!r} ne respecte pas le motif {schema['pattern']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{path} : {value} < minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{path} : {value} > maximum {schema['maximum']}")

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append(f"{path} : au moins {schema['minItems']} élément(s) requis")
            if "items" in schema:
                for i, item in enumerate(value):
                    errors += self.validate(item, schema["items"], f"{path}[{i}]")

        if isinstance(value, dict):
            props = schema.get("properties", {})
            for key in schema.get("required", []):
                if key not in value:
                    errors.append(f"{path} : propriété requise manquante « {key} »")
            addl = schema.get("additionalProperties", True)
            for key, sub in value.items():
                if key in props:
                    errors += self.validate(sub, props[key], f"{path}.{key}")
                elif addl is False:
                    errors.append(f"{path} : propriété non permise « {key} »")
                elif isinstance(addl, dict):
                    errors += self.validate(sub, addl, f"{path}.{key}")
        return errors


# --------------------------------------------------------------------------- #
# Vérifications sémantiques                                                   #
# --------------------------------------------------------------------------- #
def strings_in(obj):
    """Itère sur toutes les chaînes contenues (récursivement) dans obj."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings_in(k)
            yield from strings_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v)


def vars_in(obj) -> set[str]:
    return {m for s in strings_in(obj) for m in VAR_RE.findall(s)}


def semantic_checks(doc: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def dupes(ids, label):
        for item, n in Counter(ids).items():
            if n > 1:
                errors.append(f"Identifiant {label} dupliqué : {item}")

    ctx = doc.get("context", {})
    var_names = {v["name"] for v in ctx.get("variables", [])}
    auth_ids = {a["id"] for a in ctx.get("auth", [])}
    actor_ids = {a["id"] for a in ctx.get("actors", [])}
    td_ids = {t["id"] for t in ctx.get("testData", [])}
    dupes([v["name"] for v in ctx.get("variables", [])], "de variable")
    dupes([a["id"] for a in ctx.get("auth", [])], "d'auth")
    dupes([a["id"] for a in ctx.get("actors", [])], "d'acteur")
    dupes([t["id"] for t in ctx.get("testData", [])], "de donnée de test")

    for a in ctx.get("auth", []):
        if a.get("actorRef") and a["actorRef"] not in actor_ids:
            errors.append(f"auth {a['id']} : actorRef inconnu « {a['actorRef']} »")

    features = doc.get("features", [])
    dupes([f["id"] for f in features], "de feature")

    all_behaviors: dict[str, str] = {}
    all_interfaces: set[str] = set()
    all_tcs: dict[str, dict] = {}
    tc_list: list[dict] = []
    for f in features:
        for b in f.get("changedBehaviors", []):
            if b["id"] in all_behaviors:
                errors.append(f"Identifiant de comportement dupliqué : {b['id']}")
            all_behaviors[b["id"]] = f["id"]
            if not b["id"].startswith("B" + f["id"][1:] + "."):
                warnings.append(f"{b['id']} : préfixe attendu B{f['id'][1:]}.n dans {f['id']}")
        for i in f.get("interfaces", []):
            if i["id"] in all_interfaces:
                errors.append(f"Identifiant d'interface dupliqué : {i['id']}")
            all_interfaces.add(i["id"])
        for tc in f.get("testCases", []):
            if tc["id"] in all_tcs:
                errors.append(f"Identifiant de cas dupliqué : {tc['id']}")
            all_tcs.setdefault(tc["id"], tc)
            tc_list.append(tc)
            if not tc["id"].startswith(f"TC-{f['id']}-"):
                warnings.append(f"{tc['id']} : préfixe attendu TC-{f['id']}- dans {f['id']}")

    covered: set[str] = set()
    api_used = False

    def extracted_vars(tc: dict) -> list[list[str]]:
        """Variables extraites, appel par appel."""
        return [[e["variable"] for e in c.get("extract", [])] for c in tc.get("api", {}).get("calls", [])]

    def deps_extracted(tc: dict, seen: set[str]) -> set[str]:
        out: set[str] = set()
        for d in tc.get("dependsOn", []):
            if d in seen or d not in all_tcs:
                continue
            seen.add(d)
            for lst in extracted_vars(all_tcs[d]):
                out.update(lst)
            out |= deps_extracted(all_tcs[d], seen)
        return out

    for tc in tc_list:
        tc_id = tc["id"]
        where = tc_id
        for b in tc.get("coversBehaviors", []):
            if b not in all_behaviors:
                errors.append(f"{where} : coversBehaviors référence un comportement inconnu « {b} »")
            covered.add(b)
        if tc.get("actor") and tc["actor"] not in actor_ids:
            errors.append(f"{where} : acteur inconnu « {tc['actor']} »")
        for t in tc.get("testDataRefs", []):
            if t not in td_ids:
                errors.append(f"{where} : testDataRefs inconnu « {t} »")
        for d in tc.get("dependsOn", []):
            if d == tc_id:
                errors.append(f"{where} : dépend de lui-même")
            elif d not in all_tcs:
                errors.append(f"{where} : dependsOn inconnu « {d} »")

        # examples
        examples = tc.get("examples", [])
        ex_keys: set[str] = set()
        if examples:
            key_sets = [frozenset(e["values"].keys()) for e in examples]
            if len(set(key_sets)) > 1:
                errors.append(f"{where} : toutes les entrées de examples doivent avoir les mêmes clés")
            ex_keys = set().union(*key_sets)
            dupes([e["name"] for e in examples], f"d'exemple dans {tc_id}")

        placeholders = {p for s in strings_in(tc.get("gherkin", {})) for p in PLACEHOLDER_RE.findall(s)}
        for p in sorted(placeholders - ex_keys):
            errors.append(f"{where} : placeholder Gherkin <{p}> absent de examples")

        # api
        api = tc.get("api")
        used_in_api: set[str] = set()
        if api:
            api_used = True
            calls = api.get("calls", [])
            if not any(c["role"] == "action" for c in calls):
                warnings.append(f"{where} : aucun appel de rôle « action »")
            available = set(var_names) | ex_keys | deps_extracted(tc, {tc_id})
            for idx, call in enumerate(calls):
                cwhere = f"{where} api.calls[{idx}] ({call.get('name')})"
                if call.get("interfaceRef") and call["interfaceRef"] not in all_interfaces:
                    errors.append(f"{cwhere} : interfaceRef inconnue « {call['interfaceRef']} »")
                if call.get("auth") and call["auth"] not in auth_ids:
                    errors.append(f"{cwhere} : auth inconnue « {call['auth']} »")
                if "?" in call.get("url", ""):
                    warnings.append(f"{cwhere} : mettre les paramètres de requête dans « query », pas dans l'URL")
                if "expect" not in call and call["role"] in ("action", "verify"):
                    warnings.append(f"{cwhere} : appel {call['role']} sans « expect »")
                req_part = {k: v for k, v in call.items() if k not in ("extract",)}
                for v in vars_in(req_part):
                    used_in_api.add(v)
                    if v.startswith("$"):
                        continue  # variables dynamiques Postman ({{$guid}}, {{$timestamp}}...)
                    if v not in available:
                        errors.append(
                            f"{cwhere} : variable {{{{{v}}}}} non déclarée (context.variables), "
                            f"non extraite par un appel précédent, ni fournie par examples"
                        )
                for e in call.get("extract", []):
                    available.add(e["variable"])
        elif tc.get("level") == "api":
            warnings.append(f"{where} : level=api mais aucun bloc « api »")

        for k in sorted(ex_keys - placeholders - used_in_api):
            warnings.append(f"{where} : clé d'exemple « {k} » utilisée ni dans gherkin ni dans api")

        if not tc.get("expectedResult", "").strip():
            errors.append(f"{where} : expectedResult vide")

    # cycles de dépendances
    def has_cycle(node, stack, done):
        if node in stack:
            return True
        if node in done or node not in all_tcs:
            return False
        stack.add(node)
        if any(has_cycle(d, stack, done) for d in all_tcs[node].get("dependsOn", [])):
            return True
        stack.discard(node)
        done.add(node)
        return False

    done: set[str] = set()
    for tc_id in all_tcs:
        if has_cycle(tc_id, set(), done):
            errors.append(f"Cycle de dépendances détecté impliquant {tc_id}")
            break

    for b, fid in all_behaviors.items():
        if b not in covered:
            warnings.append(f"Comportement {b} ({fid}) couvert par aucun cas de test")

    if api_used and "baseUrl" not in var_names:
        warnings.append("Des appels API existent mais la variable « baseUrl » n'est pas déclarée")

    for f in features:
        if not any(tc.get("priority") == "P1" for tc in f.get("testCases", [])):
            warnings.append(f"{f['id']} : aucun cas P1")

    return errors, warnings


def stats(doc: dict) -> str:
    tcs = [tc for f in doc.get("features", []) for tc in f.get("testCases", [])]
    by_prio = Counter(tc.get("priority") for tc in tcs)
    by_type = Counter(tc.get("type") for tc in tcs)
    by_feat = [(f["id"], f["name"], len(f.get("testCases", []))) for f in doc.get("features", [])]
    api_count = sum(1 for tc in tcs if tc.get("api"))
    lines = [
        f"Cas de tests : {len(tcs)} (dont {api_count} exécutables via API)",
        "Par priorité : " + ", ".join(f"{k}={by_prio[k]}" for k in sorted(by_prio)),
        "Par type : " + ", ".join(f"{k}={v}" for k, v in by_type.most_common()),
        "Par feature :",
        *[f"  {fid} {name} : {n}" for fid, name, n in by_feat],
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    ap.add_argument("--strict", action="store_true", help="traiter les avertissements comme des erreurs")
    args = ap.parse_args()

    try:
        doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERREUR : lecture/parse JSON impossible : {exc}")
        return 1
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    errors = SchemaValidator(schema).validate(doc, schema)
    warnings: list[str] = []
    if not errors:  # les vérifications sémantiques supposent une structure valide
        errors, warnings = semantic_checks(doc)

    for e in errors:
        print(f"ERREUR  {e}")
    for w in warnings:
        print(f"AVERT.  {w}")

    if errors or (args.strict and warnings):
        print(f"\nÉCHEC : {len(errors)} erreur(s), {len(warnings)} avertissement(s)")
        return 1
    print(stats(doc))
    print(f"\nOK ({len(warnings)} avertissement(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
