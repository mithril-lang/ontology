# /// script
# requires-python = ">=3.12"
# dependencies = ["edn-format>=0.7.5", "rdflib>=7.1"]
# ///
"""DM2 2.02 の source extract から OWL/SHACL の Turtle と JSON を生成する。

    uv run scripts/gen_dm2_ttl.py          # ontology/dm2-2.02.ttl と ontology/dm2-2.02.json を書く
    uv run scripts/gen_dm2_ttl.py --check  # 書かずに、生成結果が commit 済みのファイルと一致するかだけ見る

scripts/gen-dm2.cljk（.mith を出す生成器）と同じ導出規則を Python で持つ。入力は同じ
source/dm2-2.02.edn、IRI も同じ（https://mithril.fund/ontology/dm2/2.02#<Term>）。
.mith を読まずに TS / Python / Iceberg 側で DM2 を使えるようにするための出口。

IDEAS 形式意味論の表現（MITHRIL-2320）:
- EA connector の両端が in-model か external かにかかわらず全 subsumption を出す。
  in-model 外の端は owl 宣言＋ :external 由来注記つきで宣言する（39 件）。
- 辞書綴り superSubType と EA 綴り superSubtype は同一概念として正規化する
  （EA 側の 1 概念に対する表記ゆれ。:resolutions に記録）。
- powertypeInstance 106 件・typeInstance 6 件は ideas 名前空間の triple として出す。
  空 subject の 3 件は表現不能（:empty-source-names に記録）。
- TupleType/tuple の property-subclass-of-class 2 件は OWL punning
  （同一 IRI を Class＋ObjectProperty 宣言）で出す。
- place3Type/placeType（n-ary）は ideas 述語の triple として出す。
- place 型に association が来る場合（WholePartType）は被参照側にも Class facet を足す
  （punning）。Mithril form 面は :rdfs/:owl/:sh の既定 key しか持てないため、
  ideas triple 自体は TTL/JSON/views に置き、.mith は RDFS backbone＋SHACL を担う。
  面分担は README の Surfaces 節に書く。

終了コード: 0 = 生成（または --check で一致）/ 1 = 件数・参照の検査に失敗 / 3 = --check で差分あり。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import edn_format
from rdflib import OWL, RDF, RDFS, SH, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source" / "dm2-2.02.edn"
OUT_TTL = ROOT / "ontology" / "dm2-2.02.ttl"
OUT_JSON = ROOT / "ontology" / "dm2-2.02.json"

BASE = "https://mithril.fund/ontology/dm2/2.02"
DM2 = Namespace(BASE + "#")
SHAPES = Namespace(BASE + "/shapes#")
IDEAS = Namespace(BASE + "/ideas#")
ONTOLOGY_IRI = URIRef(BASE)

# 辞書綴り -> EA 綴りの正規化。EA 側の 1 概念に対する既知の表記ゆれのみ。
# 新たな綴り違いはここに足すのではなく gaps として残すこと。
NORMALIZATIONS = {"superSubtype": "superSubType"}

# Pun する（Class facet を足す）in-model association。
# - TupleType/tuple: EA が class（Type/Thing）の subtype にしているため。
# - place 型として参照される association（WholePartType）は Class としても宣言する。
_EXTRA_CLASS_FACET_REASONS = {
    "TupleType": "EA asserts TupleType as a subtype of the class Type (property-subclass-of-class); OWL punning",
    "tuple": "EA asserts tuple as a subtype of the class Thing (property-subclass-of-class); OWL punning",
    "WholePartType": "referenced as a place type; associations used as types gain a Class facet (punning)",
}

# README の Layers 節と gen-dm2.cljk の self-check が主張する件数。変わったら理由を README に書くこと。
EXPECTED = {
    "classes": 196,
    "properties": 100,
    "class_edges": 205,
    "property_edges": 103,
    "domains": 86,
    "ranges": 88,
    "shapes": 83,
}


def plain(x):
    """edn_format の型を素の Python 型へ。Keyword は ':' なしの文字列にする。"""
    if isinstance(x, edn_format.Keyword):
        return x.name
    if isinstance(x, dict) or type(x).__name__ == "ImmutableDict":
        return {plain(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)) or type(x).__name__ == "ImmutableList":
        return [plain(v) for v in x]
    return x


def load_source() -> dict:
    return plain(edn_format.loads(SOURCE.read_text(encoding="utf-8")))


def _norm(n: str) -> str:
    return NORMALIZATIONS.get(n, n)


def derive(src: dict) -> dict:
    """gen-dm2.cljk の derive-axioms と同じ規則。"""
    terms = src["terms"]
    is_assoc = {t["name"]: bool(t["association?"]) for t in terms}
    in_model = set(is_assoc)

    edges = [(_norm(a), _norm(b)) for a, b in src["super-subtype"]]
    places = {_norm(k): v for k, v in src["tuple-places"].items()}
    owners = set(places)

    # --- 外部宣言 facet の決定（2 pass＋fixpoint）。gen-dm2.cljk と同一規則。
    facet: dict[str, str] = {}  # name -> "class" | "property"

    def counterparts(n: str) -> list[str]:
        out = []
        for a, b in edges:
            if a == n and b in in_model:
                out.append(b)
            elif b == n and a in in_model:
                out.append(a)
        return out

    for n in sorted(owners - in_model - {""}):
        facet[n] = "property"
    for n in sorted({e for p in edges for e in p} - in_model - {""} - set(facet)):
        cps = counterparts(n)
        if cps and all(is_assoc[c] for c in cps):
            facet[n] = "property"
        else:
            facet[n] = "class"
    for v in (pv for p in places.values() for k, pv in p.items()
              if k in ("place1Type", "place2Type") and pv and pv not in in_model and pv not in owners):
        facet.setdefault(v, "class")
    changed = True
    while changed:
        changed = False
        for a, b in edges:
            if not a or not b or a in in_model or b in in_model:
                continue
            if a in facet and b not in facet:
                facet[b] = facet[a]
                changed = True
            elif b in facet and a not in facet:
                facet[a] = facet[b]
                changed = True

    def is_class(n: str) -> bool:
        if n in in_model:
            return not is_assoc[n]
        return facet.get(n) == "class"

    def is_prop(n: str) -> bool:
        if n in in_model:
            return is_assoc[n]
        return facet.get(n) == "property"

    punned = {n for n in _EXTRA_CLASS_FACET_REASONS if n in in_model or n in facet}

    def declared(n: str) -> bool:
        return bool(n) and (n in in_model or n in facet)

    sub_class: dict[str, list[str]] = {}
    sub_prop: dict[str, list[str]] = {}
    empty_ends = []
    for sub, sup in edges:
        if not sub or not sup:
            empty_ends.append([sub, sup])
            continue
        if sub in punned and is_class(sup):
            sub_class.setdefault(sub, []).append(sup)
        elif is_prop(sub) or is_prop(sup):
            sub_prop.setdefault(sub, []).append(sup)
        else:
            sub_class.setdefault(sub, []).append(sup)

    dom_rng: dict[str, dict[str, str]] = {}
    prop_nodes = sorted([n for n in in_model if is_assoc[n]] + [n for n, f in facet.items() if f == "property"])
    for n in prop_nodes:
        p = places.get(n, {})
        entry = {}
        d, r = p.get("place1Type"), p.get("place2Type")
        if d and declared(d) and (is_class(d) or d in punned):
            entry["domain"] = d
        if r and declared(r) and (is_class(r) or r in punned):
            entry["range"] = r
        dom_rng[n] = entry

    # --- IDEAS instance links（空 subject は表現不能として記録）。
    powertype = [[a, b] for a, b in src["powertype-instance"]]
    type_inst, type_empty = [], []
    for a, b in src["type-instance"]:
        (type_inst if a else type_empty).append([a, b])
    nary = {"place3": [], "place": []}
    for k, v in places.items():
        if "place3Type" in v:
            nary["place3"].append([k, v["place3Type"]])
        if "placeType" in v:
            nary["place"].append([k, v["placeType"]])

    empty_names = sorted({*_empty_owner(places), *[f"type-instance {a}>{b}" for a, b in type_empty]})
    return {
        "facet": facet, "punned": sorted(punned), "sub_class": sub_class, "sub_prop": sub_prop,
        "dom_rng": dom_rng, "powertype": powertype, "type_inst": type_inst,
        "nary": nary, "empty_names": empty_names,
    }


def _empty_owner(places: dict) -> list[str]:
    return [f"tuple-place owner '' {v}" for k, v in places.items() if not k]


def build(src: dict, ax: dict) -> tuple[Graph, dict]:
    g = Graph()
    g.bind("dm2", DM2)
    g.bind("dm2sh", SHAPES)
    g.bind("ideas", IDEAS)
    g.bind("owl", OWL)
    g.bind("sh", SH)
    g.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    g.add((ONTOLOGY_IRI, OWL.versionInfo, Literal(src["dm2/version"])))
    g.add((ONTOLOGY_IRI, RDFS.comment, Literal("Generated from source/dm2-2.02.edn by scripts/gen_dm2_ttl.py.")))
    for pred, comment in (
        (IDEAS.powertypeInstance, "IDEAS powertypeInstance: a Type to its powertype."),
        (IDEAS.typeInstance, "IDEAS typeInstance: an Individual to its Type."),
        (IDEAS.place3Type, "Third place type of an n-ary DM2 tuple; OWL has no ternary domain/range."),
        (IDEAS.placeType, "Unary place type of a DM2 tuple; OWL has no unary domain/range."),
    ):
        g.add((pred, RDF.type, OWL.ObjectProperty))
        g.add((pred, RDFS.comment, Literal(comment)))

    terms = {t["name"]: t for t in src["terms"]}
    facet = ax["facet"]
    punned = set(ax["punned"])
    in_model = set(terms)

    def external_note(n: str) -> str:
        return ("External to the DM2 in-model dictionary set; referenced by EA connectors. "
                "Kept so every EA connector is expressed instead of dropped.")

    classes, properties, shapes = [], [], []
    all_class_names = sorted([n for n in in_model if not terms[n]["association?"]]
                             + [n for n, f in facet.items() if f == "class"]
                             + [n for n in punned])
    for n in all_class_names:
        iri = DM2[n]
        g.add((iri, RDF.type, OWL.Class))
        if n in terms:
            g.add((iri, RDFS.label, Literal(n)))
            g.add((iri, RDFS.comment, Literal(terms[n]["definition"])))
            kind = src.get("ideas-kind", {}).get(n)
            if n == "superSubType":
                kind = "IDEAS:TupleType"  # EA 綴り superSubtype の正規化先
            data_groups = terms[n].get("data-groups", [])
            external = False
        else:
            g.add((iri, RDFS.label, Literal(n)))
            g.add((iri, RDFS.comment, Literal(external_note(n))))
            kind, data_groups, external = None, [], True
        for sup in ax["sub_class"].get(n, []):
            g.add((iri, RDFS.subClassOf, DM2[sup]))
        classes.append(
            {
                "iri": str(iri),
                "name": n,
                "sub_class_of": [str(DM2[s]) for s in ax["sub_class"].get(n, [])],
                "data_groups": data_groups,
                "ideas_kind": kind,
                "external": external,
            }
        )

    all_prop_names = sorted([n for n in in_model if terms[n]["association?"]]
                            + [n for n, f in facet.items() if f == "property"])
    for n in all_prop_names:
        iri = DM2[n]
        g.add((iri, RDF.type, OWL.ObjectProperty))
        if n in terms:
            g.add((iri, RDFS.label, Literal(n)))
            g.add((iri, RDFS.comment, Literal(terms[n]["definition"])))
            kind = src.get("ideas-kind", {}).get(n)
            if n == "superSubType":
                kind = "IDEAS:TupleType"
            external = False
        else:
            g.add((iri, RDFS.label, Literal(n)))
            g.add((iri, RDFS.comment, Literal(external_note(n))))
            kind, external = None, True
        dr = ax["dom_rng"].get(n, {})
        for sup in ax["sub_prop"].get(n, []):
            g.add((iri, RDFS.subPropertyOf, DM2[sup]))
        if "domain" in dr:
            g.add((iri, RDFS.domain, DM2[dr["domain"]]))
        if "range" in dr:
            g.add((iri, RDFS.range, DM2[dr["range"]]))
        properties.append(
            {
                "iri": str(iri),
                "name": n,
                "sub_property_of": [str(DM2[s]) for s in ax["sub_prop"].get(n, [])],
                "domain": str(DM2[dr["domain"]]) if "domain" in dr else None,
                "range": str(DM2[dr["range"]]) if "range" in dr else None,
                "ideas_kind": kind,
                "external": external,
            }
        )
        if "domain" in dr and "range" in dr:
            shape, pshape = SHAPES[n], SHAPES[n + "-property"]
            g.add((shape, RDF.type, SH.NodeShape))
            g.add((shape, SH.targetClass, DM2[dr["domain"]]))
            g.add((shape, SH.property, pshape))
            g.add((pshape, SH.path, iri))
            g.add((pshape, getattr(SH, "class"), DM2[dr["range"]]))
            shapes.append(
                {"iri": str(shape), "target_class": str(DM2[dr["domain"]]), "path": str(iri),
                 "class": str(DM2[dr["range"]])}
            )

    # --- IDEAS instance links と n-ary places。
    for a, b in ax["powertype"]:
        g.add((DM2[a], IDEAS.powertypeInstance, DM2[b]))
    for a, b in ax["type_inst"]:
        g.add((DM2[a], IDEAS.typeInstance, DM2[b]))
    for k, v in ax["nary"]["place3"]:
        g.add((DM2[k], IDEAS.place3Type, DM2[v]))
    for k, v in ax["nary"]["place"]:
        g.add((DM2[k], IDEAS.placeType, DM2[v]))

    kinds = {}
    for n in sorted(in_model):
        k = src.get("ideas-kind", {}).get(n)
        if n == "superSubType":
            k = "IDEAS:TupleType"
        if k:
            kinds[str(DM2[n])] = k
    doc = {
        "dm2_version": src["dm2/version"],
        "base": BASE,
        "namespaces": {"ideas": str(IDEAS)},
        "generated_from": "source/dm2-2.02.edn",
        "generated_by": "scripts/gen_dm2_ttl.py",
        "classes": classes,
        "properties": properties,
        "shapes": shapes,
        "ideas_relations": {
            "powertype_instance": [[str(DM2[a]), str(DM2[b])] for a, b in ax["powertype"]],
            "type_instance": [[str(DM2[a]), str(DM2[b])] for a, b in ax["type_inst"]],
            "place3": [[str(DM2[a]), str(DM2[b])] for a, b in ax["nary"]["place3"]],
            "place": [[str(DM2[a]), str(DM2[b])] for a, b in ax["nary"]["place"]],
        },
        "ideas_kinds": kinds,
        "resolutions": {
            "normalizations": [{"from": k, "to": v, "reason": "EA spelling; dictionary spells superSubType"}
                               for k, v in NORMALIZATIONS.items()],
            "external_declarations": [{"name": n, "facet": f} for n, f in sorted(facet.items())],
            "empty_source_names": ax["empty_names"],
        },
    }
    return g, doc


def check(ax: dict, doc: dict) -> list[str]:
    declared = {c["iri"] for c in doc["classes"]} | {p["iri"] for p in doc["properties"]}
    refs = [s for c in doc["classes"] for s in c["sub_class_of"]]
    refs += [s for p in doc["properties"] for s in p["sub_property_of"]]
    refs += [p[k] for p in doc["properties"] for k in ("domain", "range") if p[k]]
    dangling = [r for r in refs if r not in declared]
    counts = {
        "classes": len(doc["classes"]),
        "properties": len(doc["properties"]),
        "class_edges": sum(len(v) for v in ax["sub_class"].values()),
        "property_edges": sum(len(v) for v in ax["sub_prop"].values()),
        "domains": sum(1 for p in doc["properties"] if p["domain"]),
        "ranges": sum(1 for p in doc["properties"] if p["range"]),
        "shapes": len(doc["shapes"]),
    }
    for k, v in counts.items():
        print(f"COUNT\t{k}\t{v}")
    print(f"COUNT\tdangling-iris\t{len(dangling)}")
    print(f"COUNT\tpowertype-instance\t{len(doc['ideas_relations']['powertype_instance'])}")
    print(f"COUNT\ttype-instance\t{len(doc['ideas_relations']['type_instance'])}")
    errors = [f"{k}: {counts[k]} != expected {EXPECTED[k]}" for k in EXPECTED if EXPECTED[k] and counts[k] != EXPECTED[k]]
    errors += [f"dangling IRI {r}" for r in dangling[:5]]
    errors += [f"ideas facet undeclared {n}" for n in ax["facet"] if str(DM2[n]) not in declared]
    return errors


def main(argv: list[str]) -> int:
    src = load_source()
    ax = derive(src)
    g, doc = build(src, ax)
    errors = check(ax, doc)
    if errors:
        for e in errors:
            print(f"FAIL\t{e}", file=sys.stderr)
        return 1
    ttl = g.serialize(format="turtle")
    js = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if "--check" in argv:
        stale = [p.name for p, body in ((OUT_TTL, ttl), (OUT_JSON, js)) if not p.exists() or p.read_text() != body]
        for name in stale:
            print(f"STALE\t{name}", file=sys.stderr)
        return 3 if stale else 0
    OUT_TTL.write_text(ttl, encoding="utf-8")
    OUT_JSON.write_text(js, encoding="utf-8")
    print(f"WROTE\t{OUT_TTL.relative_to(ROOT)}\t{len(g)} triples")
    print(f"WROTE\t{OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
