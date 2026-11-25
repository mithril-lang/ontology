# AGENTS.md — mithril-lang/ontology

- Purpose: DoDAF 2.02 DM2 vocabulary in Mithril, with generated Turtle and JSON outputs.
- Owner: Platform Engineering (Jun Kawasaki, @com-junkawasaki).
- Visibility: public. Do not change it without Jun's GO.
- Separate-repository reason: Public OSS library reused outside Mithril and pinned by mithril-fund (policy section 4, reason 3).
- Verification: Regenerate with the scripts in `scripts/` as described in the README and confirm the generated files do not change.
- Release path: No deployment. mithril-fund pins a commit in `ontology/dm2/2.02/PIN.json`.

Rules: merge with a merge commit (no squash or rebase). Never commit secrets,
customer data or real target details. Run `gitleaks git --redact` before
pushing when it is installed.

Repository rules and classification: [mithril-fund repository policy](https://github.com/mithril-lang/mithril-fund/blob/main/docs/operations/repository-policy.md)
(`docs/operations/repository-policy.md` in mithril-fund).
