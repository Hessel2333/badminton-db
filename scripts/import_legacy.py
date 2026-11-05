#!/usr/bin/env python3
"""One-time, metadata-only migration from the existing tracker catalog.

No photos, app databases, backups, personal notes, or environment files are copied.
Run only against an empty product directory; curated records are never overwritten.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"球拍": "racket", "羽毛球": "shuttlecock", "球鞋": "shoes", "其他": "other"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def png_info(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    width, height = struct.unpack(">II", data[16:24])
    alpha = data[25] in (4, 6)
    pos = 8
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"tRNS":
            alpha = True
        pos += length + 12
    return {"width": width, "height": height}, alpha


def migrate(source):
    products_dir = ROOT / "data/products"
    if products_dir.exists() and any(products_dir.rglob("*.json")):
        raise SystemExit("Refusing to overwrite existing product records")
    catalog = source / "catalog"
    images_dir = source / "ios/BadmintonTracker/BadmintonTracker/Resources/GearImages"
    image_map = read(images_dir / "gear-image-manifest.json")["images"]
    brands = read(catalog / "brands.json")["brands"]
    groups = [read(p) for p in sorted((catalog / "equipment").glob("*.json"))]
    originals = [e for g in groups for e in g["equipment"]]
    snapshot_hash = digest(json.dumps({"brands": brands, "equipment": originals}, ensure_ascii=False, sort_keys=True).encode())
    import_by_id = {}
    for p in sorted((catalog / "imports").glob("*.json")):
        if p.name == "2026-11-05-victor-cylinder.json":
            record_id = "victor-cylinder-v3"
        elif p.name == "2026-11-05-yonex-as.json":
            record_id = "yonex-as-cutouts-2026-11-05"
        else:
            record_id = "legacy-image-processing"
        for entry in read(p).get("items", []):
            import_by_id[entry["id"]] = (record_id, entry)

    source_records = [
        {"id": "legacy-catalog-v8", "title": "Existing badminton equipment catalog, snapshot 8", "type": "curated-import", "url": "https://github.com/Hessel2333/badminton_tracker", "retrievedAt": "2026-11-05", "verification": "unverified", "notes": "Imported from a maintained catalog snapshot. This is provenance for the import, not manufacturer verification. Reference-price dates and primary product URLs require review.", "snapshotSha256": snapshot_hash},
        {"id": "victor-cylinder-v3", "title": "VICTOR cylindrical packaging reconstruction, revision 3", "type": "processing-record", "url": None, "retrievedAt": "2026-11-05", "verification": "unverified", "notes": "User-provided manufacturer-reference photos informed a generated paper/light master and fixed vector artwork. Graphics use front-half cylindrical projection. Red approval stickers were removed. Barcode 1234567890128 is illustrative. Redistribution permission for third-party artwork is not established.", "snapshotSha256": None},
        {"id": "yonex-as-cutouts-2026-11-05", "title": "YONEX AS-series cutout processing record", "type": "processing-record", "url": None, "retrievedAt": "2026-11-05", "verification": "unverified", "notes": "Image-generation-assisted background extraction from supplied product images. Origin and redistribution permission require review; no image binaries are included.", "snapshotSha256": None},
        {"id": "legacy-image-processing", "title": "Earlier equipment-photo processing record", "type": "processing-record", "url": None, "retrievedAt": "2026-11-05", "verification": "unverified", "notes": "Earlier imported photos and geometry-based cutouts. Original publication URLs and permission require review; no image binaries are included.", "snapshotSha256": None},
    ]
    for record in source_records:
        write(ROOT / "data/sources" / (record["id"] + ".json"), {"$schema": "../../schemas/source.schema.json", **record})
    for brand in brands:
        write(ROOT / "data/brands" / (brand["id"] + ".json"), {
            "$schema": "../../schemas/brand.schema.json", **brand, "website": None,
            "provenance": {"sourceIds": ["legacy-catalog-v8"], "verification": "unverified", "fieldSources": {}},
        })

    used_slugs, asset_ids, product_ids = set(), [], []
    for entry in originals:
        key = entry.get("imageKey")
        stem = re.sub(r"_(?:main|cutout)_\d+$", "", key or "")
        prefix = entry["brandId"] + "_" + CATEGORIES[entry["category"]] + "_"
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
        model_slug = slug(stem or entry.get("model") or "") or "product-" + entry["id"][:8]
        product_slug = entry["brandId"] + "-" + model_slug
        if product_slug in used_slugs:
            raise ValueError("Duplicate product slug: " + product_slug)
        used_slugs.add(product_slug)
        media_ids = []
        if key:
            aid = slug(key)
            file_name = image_map[key]
            pixels = (images_dir / file_name).read_bytes()
            dimensions, alpha = png_info(pixels)
            record_id, row = import_by_id.get(entry["id"], (None, {}))
            processing = row.get("processing")
            is_render = record_id == "victor-cylinder-v3"
            original_name = row.get("fileName")
            original_hash = row.get("originalSha256")
            if original_name and not original_hash:
                subdir = {"racket": "rackets", "shuttlecock": "shuttlecocks", "shoes": "shoes"}.get(CATEGORIES[entry["category"]], "other")
                original_path = source / "assets/gear_image/original" / subdir / original_name
                if original_path.is_file():
                    original_hash = digest(original_path.read_bytes())
            asset = {
                "$schema": "../../schemas/asset.schema.json", "id": aid, "productIds": [entry["id"]],
                "kind": "generated-render" if is_render else "processed-image", "role": "primary",
                "fileName": file_name, "legacyImageKeys": sorted(k for k, v in image_map.items() if v == file_name),
                "dimensions": dimensions, "sha256": digest(pixels), "hasAlpha": alpha, "isOfficial": False,
                "provenance": {"sourceIds": ["legacy-catalog-v8"] + ([record_id] if record_id else []), "method": processing,
                    "derivedFrom": [{"fileName": original_name, "sha256": original_hash, "kind": "reported-official-reference" if is_render else "unknown-origin"}] if original_name else []},
                "rights": {"status": "unreviewed", "license": None, "holder": None, "evidenceUrl": None},
                "distribution": {"status": "withheld", "file": None},
                "syntheticIdentifiers": [{"value": "1234567890128", "format": "EAN-13", "purpose": "illustrative-only"}] if is_render else [],
                "notes": ["Redistribution permission has not been established; image binary is not distributed."] + (["Reconstructed packaging illustration, not a manufacturer-issued product photo."] if is_render else []),
            }
            write(ROOT / "media/metadata" / (aid + ".json"), asset)
            media_ids.append(aid)
            asset_ids.append(aid)

        price = entry.get("suggestedUnitPriceCny")
        product = {
            "$schema": "../../../schemas/product.schema.json", "id": entry["id"], "slug": product_slug,
            "brandId": entry["brandId"], "category": CATEGORIES[entry["category"]],
            "names": {"zh-CN": entry["name"], "en": entry.get("nameEn")}, "model": entry.get("model"), "series": entry.get("series"), "aliases": entry.get("aliases", []),
            "variant": {"label": entry.get("variant"), "generation": entry.get("generation"), "color": entry.get("color")},
            "specifications": {"weightClass": entry.get("weightClass"), "gripSize": entry.get("gripSize"), "releaseYear": entry.get("releaseYear")},
            "relations": {"variantOf": None}, "mediaIds": media_ids,
            "provenance": {"sourceIds": ["legacy-catalog-v8"], "verification": "unverified", "fieldSources": {}},
            "curation": {"listed": entry["isActive"], "tags": entry["tags"]},
            "priceObservations": [{"kind": "legacy-reference", "amount": price, "currency": "CNY", "region": "CN", "observedAt": None, "verification": "unverified", "sourceIds": ["legacy-catalog-v8"]}] if price is not None else [],
            "legacy": {"imageKey": key, "popularity": entry["popularity"], "revision": entry["revision"], "createdAt": entry["createdAt"], "updatedAt": entry["updatedAt"]},
            "revision": 1,
        }
        write(products_dir / entry["brandId"] / (model_slug + ".json"), product)
        product_ids.append(entry["id"])
    write(ROOT / "media/manifest.json", {"schemaVersion": 1, "metadataIds": sorted(asset_ids), "policy": "Only approved, explicitly licensed image files are distributed. Withheld records contain metadata only."})
    write(ROOT / "docs/migration.json", {"sourceCatalogVersion": 8, "dataVersion": "0.1.0", "importedOn": "2026-11-05", "sourceSnapshotSha256": snapshot_hash, "brands": len(brands), "products": len(product_ids), "mediaMetadata": len(asset_ids), "imageBinariesCopied": 0, "preservedProductIds": sorted(product_ids)})
    print(f"Imported {len(product_ids)} products, {len(brands)} brands, {len(asset_ids)} media metadata records; copied 0 images")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    migrate(parser.parse_args().source.resolve())
