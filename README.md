# DoDAF 2.02 DM2 vocabulary in Mithril

This repository is the Mithril source for a vocabulary projection of the official DoDAF Meta-Model (DM2) 2.02 Data Dictionary. The source file is [`ontology/dodaf-v2-02.mith`](ontology/dodaf-v2-02.mith).

## Source and mapping rules

The projection was generated from the official [DM2 Data Dictionary and Model Files](https://dowcio.war.gov/Library/DoD-Architecture-Framework/dodaf20_logical/), specifically `DM2_Data_Dictionary_and_Mappings_v202.xls` (SHA-256 `7ff87dd7db559c1402987674478f1204d54586fe4025dec96fcfe0631e8aec0e`). It includes every row marked `a. In Model`: 254 terms, with the official term spelling and definition. The dictionary's `Association?` flag determines whether each entry is represented as an OWL object property (81 entries) or class (173 entries). Deleted, alias/composite, external, and new dictionary-only entries are excluded.

The DoD source provides the controlled terms and EA model, but does not publish a stable public RDF namespace for these terms. The IRIs in this projection are therefore local identifiers under `https://mithril.fund/ontology/dm2/2.02#`; the `name` and `description` values retain the official DM2 vocabulary. They must not be mistaken for DoD-issued IRIs.

This is a faithful term-and-definition projection, not the complete formal DM2/IDEAS logical model and not a DoDAF conformance claim. The official model includes more formal structure, including typed associations and IDEAS semantics, and DoDAF conformance also requires transfer in accordance with PES. Those layers are not asserted by this file.

## Fund–Mithril mapping

DM2 2.02 has no in-model `Fund`, `Funding`, or `ResourceFlow` term. `Cost` is listed as an alias/composite, not as an in-model concept. The model therefore uses only these official DM2 concepts when describing the domain:

- Mithril work can be represented as a `Project`.
- A concrete funding action can be represented as an `Activity`.
- Resources consumed or produced by an activity use `Resource`, `activityConsumesResource`, and `activityProducesResource`.
- Cost is not a standalone DM2 class or relationship; a financial amount needs a domain-specific measurement mapping and source evidence.

This does not assert that a fund transfer occurred or that a monetary fund is a DM2 `Resource`. Those claims need an explicit domain classification and evidence. No Fund-specific DM2 terms are minted here.

## Compile

Compile with the Mithril compiler from [`mithril-lang/mithril`](https://github.com/mithril-lang/mithril):

```sh
kbb --backend sci --classpath "$(clojure -Spath)" \
  bin/mithril.cljk compile-ontology ontology/dodaf-v2-02.mith
```

The `.mith` document is the canonical authored source.
