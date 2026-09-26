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
ONTOLOGY_IRI = URIRef(BASE)

# README の Layers 節と gen-dm2.cljk の self-check が主張する件数。変わったら理由を README に書くこと。
EXPECTED = {
    "classes": 173,
    "properties": 81,
    "class_edges": 182,
    "property_edges": 81,
    "domains": 67,
    "ranges": 66,
    "shapes": 62,
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


def derive(src: dict) -> dict:
    """gen-dm2.cljk の derive-axioms と同じ規則。"""
    terms = src["terms"]
    is_assoc = {t["name"]: bool(t["association?"]) for t in terms}

    def is_class(n):
        return n in is_assoc and not is_assoc[n]

    def is_prop(n):
        return n in is_assoc and is_assoc[n]

    sub_class: dict[str, list[str]] = {}
    sub_prop: dict[str, list[str]] = {}
    edge_gaps = []
    for sub, sup in src["super-subtype"]:
        if is_class(sub) and is_class(sup):
            sub_class.setdefault(sub, []).append(sup)
        elif is_prop(sub) and is_prop(sup):
            sub_prop.setdefault(sub, []).append(sup)
        else:
            reason = (
                "an end is not an in-model dictionary term"
                if not (sub in is_assoc and sup in is_assoc)
                else "association is a subtype of a non-association class"
            )
            edge_gaps.append({"sub": sub, "super": sup, "reason": reason})

    places = src["tuple-places"]
    dom_rng: dict[str, dict[str, str]] = {}
    for t in terms:
        if not t["association?"]:
            continue
        p = places.get(t["name"], {})
        d, r = p.get("place1Type"), p.get("place2Type")
        entry = {}
        if is_class(d):
            entry["domain"] = d
        if is_class(r):
            entry["range"] = r
        dom_rng[t["name"]] = entry

    return {"sub_class": sub_class, "sub_prop": sub_prop, "dom_rng": dom_rng, "edge_gaps": edge_gaps}


def build(src: dict, ax: dict) -> tuple[Graph, dict]:
    g = Graph()
    g.bind("dm2", DM2)
    g.bind("dm2sh", SHAPES)
    g.bind("owl", OWL)
    g.bind("sh", SH)
    g.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    g.add((ONTOLOGY_IRI, OWL.versionInfo, Literal(src["dm2/version"])))
    g.add((ONTOLOGY_IRI, RDFS.comment, Literal("Generated from source/dm2-2.02.edn by scripts/gen_dm2_ttl.py.")))

    classes, properties, shapes = [], [], []
    for t in src["terms"]:
        n = t["name"]
        iri = DM2[n]
        g.add((iri, RDFS.label, Literal(n)))
        g.add((iri, RDFS.comment, Literal(t["definition"])))
        if t["association?"]:
            g.add((iri, RDF.type, OWL.ObjectProperty))
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
        else:
            g.add((iri, RDF.type, OWL.Class))
            for sup in ax["sub_class"].get(n, []):
                g.add((iri, RDFS.subClassOf, DM2[sup]))
            classes.append(
                {
                    "iri": str(iri),
                    "name": n,
                    "sub_class_of": [str(DM2[s]) for s in ax["sub_class"].get(n, [])],
                    "data_groups": t.get("data-groups", []),
                }
            )

    doc = {
        "dm2_version": src["dm2/version"],
        "base": BASE,
        "generated_from": "source/dm2-2.02.edn",
        "generated_by": "scripts/gen_dm2_ttl.py",
        "classes": classes,
        "properties": properties,
        "shapes": shapes,
        "axiom_gaps": {"edges": ax["edge_gaps"]},
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
    errors = [f"{k}: {counts[k]} != expected {EXPECTED[k]}" for k in EXPECTED if counts[k] != EXPECTED[k]]
    errors += [f"dangling IRI {r}" for r in dangling[:5]]
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
