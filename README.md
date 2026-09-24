# DoDAF 2.02 DM2 vocabulary in Mithril

This repository is the Mithril source for a projection of the official DoDAF Meta-Model (DM2) 2.02. It covers the Data Dictionary terms and definitions, the supertype and tuple-place structure of the official Enterprise Architect model, and the dictionary's model-to-concept mapping. The ontology is [`ontology/dodaf-v2-02.mith`](ontology/dodaf-v2-02.mith) and the viewpoint/model catalog is [`ontology/dodaf-v2-02-views.edn`](ontology/dodaf-v2-02-views.edn). Both are generated from [`source/dm2-2.02.edn`](source/dm2-2.02.edn).

## Layers

The repository has one data source and two generated outputs:

| File | Role |
|---|---|
| [`source/dm2-2.02.edn`](source/dm2-2.02.edn) | Extract of the two official DoD files (data, committed) |
| [`scripts/gen-dm2.cljk`](scripts/gen-dm2.cljk) | Deterministic generator and checker |
| [`ontology/dodaf-v2-02.mith`](ontology/dodaf-v2-02.mith) | Mithril ontology (generated) |
| [`ontology/dodaf-v2-02-views.edn`](ontology/dodaf-v2-02-views.edn) | Viewpoint / model catalog (generated) |

### Sources

Both files come from the DoD CIO [DM2 Data Dictionary and Model Files](https://dowcio.war.gov/Library/DoD-Architecture-Framework/dodaf20_logical/) page:

- `DM2_Data_Dictionary_and_Mappings_v202.xls`, SHA-256 `7ff87dd7db559c1402987674478f1204d54586fe4025dec96fcfe0631e8aec0e` ([url](https://dowcio.war.gov/Portals/0/Documents/DODAF/DM2_Data_Dictionary_and_Mappings_v202.xls)).
- `DM2_EA_v2.02.eap.zip`, SHA-256 `81617769195b6d5d5d7cda8fb3d40a8b6fdd03b14241fb9e122fddd7be480457`; inner `DM2_EA_v2.02.eap`, SHA-256 `4321f814fbf47ec84103cfccc5d162301b1993f723a11cdbfa77fddfbdc6034f` ([url](https://dowcio.war.gov/Portals/0/Documents/DODAF/DM2_EA_v2.02.eap.zip)). This is the official Sparx Enterprise Architect model; it was read with mdbtools (`mdb-export DM2_EA_v2.02.eap t_object` / `t_connector`).

The column-by-column extraction procedure is recorded under `:sources` in `source/dm2-2.02.edn`.

### 1. Terms and definitions (dictionary)

Every dictionary row marked `a. In Model` is included: 254 terms, with the official spelling and definition (column C; CRLF normalized to LF and surrounding whitespace trimmed). The dictionary's `Association?` flag decides whether a term is an OWL object property (81 terms) or a class (173 terms). Deleted, alias/composite, external and new dictionary-only entries are excluded. The `:id`, `:name` and `:description` of every node are unchanged from the earlier term-only projection.

### 2. Supertypes and tuple places (EA model)

The logical structure is taken from connectors in the EA model. It adds only what those connectors state:

- **Subtypes.** An EA `Generalization` (IDEAS `superSubtype`) between two in-model classes becomes `:rdfs/sub-class-of`. The same connector between two in-model associations becomes `:rdfs/sub-property-of`. This gives 182 class edges and 81 property edges. When a term has several supertypes, the value is a vector.
- **Tuple places.** DM2 associations are IDEAS tuple types whose places are typed by `place1Type` / `place2Type` connectors. **Convention used here: `:rdfs/domain` is the `place1Type` and `:rdfs/range` is the `place2Type`.** This is the IDEAS place order. It is not always the order that the association's English name suggests: for example, the EA gives `activityPerformedByPerformer` place1 `Performer` and place2 `Activity`. This gives 67 domains and 66 ranges.
- **SHACL.** Each association that has both places typed by in-model classes also gets a `shacl/node-shape` (IRI `https://mithril.fund/ontology/dm2/2.02/shapes#<association>`), 62 in total. It has `:sh/target-class` set to the place1 type and one property shape whose `:sh/path` is the association and whose `:sh/class` is the place2 type. No cardinality is asserted, because the EA model states none.

Some structure has no counterpart in the Mithril form surface. It is listed, with a reason, under `:axiom-gaps` in the view catalog rather than being approximated. It includes:

- 43 supertype edges with an end that is not an in-model term, such as the security-marking classes.
- 2 edges where an association is a subtype of a class (`TupleType` to `Type`, `tuple` to `Thing`).
- 8 associations with no place connectors under their exact name.
- `place3Type` / `placeType` places.
- A place typed by an association or by a term that is not in the model.
- The spelling mismatch `superSubType` (dictionary) versus `superSubtype` (EA).
- IDEAS `powertypeInstance` (106) and `typeInstance` (9). These stay in the source EDN.

### 3. View catalog (dictionary mapping)

`ontology/dodaf-v2-02-views.edn` contains the following:

- The 8 DoDAF viewpoints, with IRIs `https://mithril.fund/ontology/dm2/2.02/views#<Viewpoint>`: All, Capability, DataAndInformation, Operational, Project, Services, Standards, Systems. The names come from the [DoD CIO viewpoints page](https://dowcio.war.gov/Library/DoD-Architecture-Framework/dodaf20_viewpoints/).
- The 52 models, with IRIs `.../views#<Model-id>`, such as `#OV-4` and `#SvcV-10a`. Each model has the title and description from the dictionary header rows, its viewpoint, and `:concepts {term-IRI official-code}`.
- Per term: `:data-groups` (the dictionary's DM2 Submodel columns), `:ideas-kind` (the EA stereotype, for example `IDEAS:Powertype`) and the inverse `:models` map.

A consumer can label a page from `:title`. It can check that a view uses only its concepts by testing membership in that model's `:concepts`.

The mapping codes are `o`, `n`, `np`, `s`, `df`, `dfo`, `if` and `ifo`. They are kept verbatim. **The workbook publishes no legend for them, and none is assigned here.**

### Identity and conformance

DoD does not publish a stable public RDF namespace for DM2 terms. All IRIs here (`https://mithril.fund/ontology/dm2/2.02#`, `/shapes#` and `/views#`) are local identifiers, and must not be mistaken for DoD-issued IRIs. This repository is a machine-checkable projection of the DM2 2.02 terms, their supertype and tuple-place structure, and the dictionary's model mapping. It is not the complete IDEAS formal ontology (for example, powertypes and the 4D extensional semantics are not asserted in OWL). It makes no DoDAF conformance claim: that also requires data exchange in accordance with the PES, which is not provided here.

## Regenerate and check

```sh
kbb --backend sci scripts/gen-dm2.cljk           # write both generated files
kbb --backend sci scripts/gen-dm2.cljk --check   # regenerate in memory and compare
```

`--check` exits non-zero and names the first file and line that differ. It also re-reads the files on disk and prints `SCANNED<TAB>name<TAB>n` counts, where a zero count fails. The counts cover classes, properties, sub-class edges, domain/range pairs, shapes, viewpoints, models and descriptions equal to the source definition. The check also requires the following, and fails otherwise:

- No dangling IRIs: every IRI used by an axiom, shape or the view catalog is declared in the `.mith`.
- No IRI used as the wrong kind, for example a property used where a class is expected.
- Acyclic `subClassOf` and `subPropertyOf` graphs.

`--check --root <dir>` checks a copy.

## Fund–Mithril mapping

DM2 2.02 has no in-model `Fund`, `Funding`, or `ResourceFlow` term. `Cost` is listed as an alias/composite, not as an in-model concept. The model therefore uses only these official DM2 concepts when describing the domain:

- Mithril work can be represented as a `Project`.
- A concrete funding action can be represented as an `Activity`.
- Resources consumed or produced by an activity use `Resource`, `activityConsumesResource`, and `activityProducesResource`.
- Cost is not a standalone DM2 class or relationship; a financial amount needs a domain-specific measurement mapping and source evidence.

This does not assert that a fund transfer occurred or that a monetary fund is a DM2 `Resource`. Those claims need an explicit domain classification and evidence. No Fund-specific DM2 terms are minted here.

## Compile

Compile with the Mithril compiler from [`mithril-lang/mithril`](https://github.com/mithril-lang/mithril). Run this from a mithril checkout, where `nbb.edn` supplies the classpath:

```sh
kbb --backend sci --classpath "$(kbb -Spath)" \
  bin/mithril.cljk compile-ontology <path-to>/ontology/dodaf-v2-02.mith
```

`source/dm2-2.02.edn` is the canonical source. Both files under `ontology/` are generated from it, so do not hand-edit them. Change the source or the generator, then regenerate.
