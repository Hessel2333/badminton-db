# Contributing

Contribute through a pull request or the equipment issue template. English and
Chinese submissions are welcome. Data records should be independently useful
to clients other than the original tracker app.

## Add or correct a model

1. Choose the existing brand, or add a brand record and explicit aliases.
2. Search names, model codes and aliases before creating a new product.
3. Keep existing UUIDs. For a genuinely new entry, generate a UUID and a unique
   readable slug, then add one JSON file in the brand folder.
4. Provide sources, ideally the exact manufacturer product page. Explain which
   fields each source supports; add `fieldSources` when claims use different evidence.
5. Leave unknown details `null`. Distinguish variants and generations explicitly.
6. Update record revisions and dataset/export versions as appropriate.
7. Run validation and tests.

Do not submit private purchases, stock levels, account details, serial numbers,
backup files or personal photographs without an explicit public-data contribution.
Do not guess a generation, release year, speed, material or current price from
a filename or similar product. Unverified legacy prices must remain labeled.

## Images

Metadata-only records are welcome even when redistribution has not been cleared.
Do not upload the underlying binary until you can document permission.

To contribute an image file:

- Identify its author/rights holder, explicit license and permission evidence URL.
- Explain whether it is an original photo, cutout, generated render or derivative.
- Record original-source and processing history, plus a SHA-256 of the submitted file.
- Place it under `media/files/` and link it from a media metadata record.
- Set `distribution.status: public` only after rights have been reviewed and
  `rights.status: approved` is appropriate. State the applicable supported license.
- Label edited packaging details and illustrative identifiers accurately.

The initial supported media licenses are CC0-1.0, CC-BY-4.0, CC-BY-SA-4.0 and MIT.
Approval records must include a rights holder and evidence URL. Do not describe
a manufacturer or retailer download as openly licensed without supporting terms.
Metadata contributions are under CC BY 4.0; code/docs/schema contributions are MIT.
You may license only rights you hold or are authorized to grant.

## Checks

```sh
python -m pip install -r requirements.txt
python scripts/catalog.py validate
python -m unittest discover -s tests -v
python scripts/catalog.py build
```

Checks cover schemas, duplicate JSON keys and IDs, scoped alias conflicts,
cross-references, variant cycles, media permissions/paths/hashes, deterministic
exports and stable iOS identifiers. Changes to tools should include tests for
the consumer behavior or failure they address.
