#!/usr/bin/env python3
"""Validate, build, and package the public BadmintonDB dataset."""
import argparse
import copy
import gzip
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://hessel2333.github.io/badminton-db"
CATEGORIES = {"racket": "球拍", "shuttlecock": "羽毛球", "shoes": "球鞋", "other": "其他"}
OPEN_MEDIA_LICENSES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT"}


class CatalogError(ValueError):
    pass


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read(path):
    def reject_constant(value):
        raise CatalogError("Non-finite JSON number: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys, parse_constant=reject_constant)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def load(root=ROOT):
    paths = {
        "brands": sorted((root / "data/brands").glob("*.json")),
        "products": sorted((root / "data/products").glob("*/*.json")),
        "sources": sorted((root / "data/sources").glob("*.json")),
        "assets": sorted((root / "media/metadata").glob("*.json")),
    }
    return {"manifest": read(root / "data/manifest.json"), "paths": paths,
            **{kind: [read(p) for p in files] for kind, files in paths.items()}}


def validate(root=ROOT):
    data = load(root)
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    validators = {}
    for kind in ("manifest", "brand", "product", "source", "asset"):
        schema = read(root / "schemas" / (kind + ".schema.json"))
        Draft202012Validator.check_schema(schema)
        validators[kind] = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in validators["manifest"].iter_errors(data["manifest"]):
        errors.append("data/manifest.json: " + error.message)
    for plural, singular in [("brands", "brand"), ("products", "product"), ("sources", "source"), ("assets", "asset")]:
        for file, record in zip(data["paths"][plural], data[plural]):
            for error in validators[singular].iter_errors(record):
                errors.append(str(file.relative_to(root)) + ": " + error.message)
    if errors:
        raise CatalogError("\n".join(errors))

    maps = {}
    for kind in ("brands", "products", "sources", "assets"):
        ids = [x["id"] for x in data[kind]]
        require(len(ids) == len(set(ids)), "Duplicate " + kind + " ID")
        maps[kind] = {x["id"]: x for x in data[kind]}
    require(bool(data["brands"]) and bool(data["products"]), "Empty catalog")
    slugs = [p["slug"] for p in data["products"]]
    require(len(slugs) == len(set(slugs)), "Duplicate product slug")
    lookup, brand_lookup = {}, {}
    public_files = set()
    for brand in data["brands"]:
        for alias in [brand["name"], *brand["aliases"]]:
            key = fold(alias)
            require(bool(key), "Empty normalized brand alias")
            require(key not in brand_lookup or brand_lookup[key] == brand["id"], "Conflicting brand alias: " + alias)
            brand_lookup[key] = brand["id"]
    for product, file in zip(data["products"], data["paths"]["products"]):
        pid = product["id"]
        require(product["brandId"] in maps["brands"], pid + ": unknown brand")
        require(file.parent.name == product["brandId"], pid + ": brand folder mismatch")
        require(product["slug"].startswith(product["brandId"] + "-"), pid + ": slug must start with brand ID")
        names = [*product["names"].values(), product["model"], *product["aliases"]]
        for alias in filter(None, names):
            require(bool(fold(alias)), pid + ": empty normalized product name/alias")
            key = (product["brandId"], product["category"], fold(alias))
            require(key not in lookup or lookup[key] == pid, pid + ": conflicting scoped name/model/alias: " + alias)
            lookup[key] = pid
        for aid in product["mediaIds"]:
            require(aid in maps["assets"], pid + ": unknown media ID " + aid)
            if aid in maps["assets"]:
                require(pid in maps["assets"][aid]["productIds"], pid + ": media back-reference missing")
        parent = product["relations"]["variantOf"]
        require(parent is None or (parent in maps["products"] and parent != pid), pid + ": invalid variant parent")
        if parent in maps["products"]:
            require(maps["products"][parent]["brandId"] == product["brandId"], pid + ": cross-brand variant relation")
        for price in product["priceObservations"]:
            if price["verification"] == "verified":
                require(price["observedAt"] is not None, pid + ": verified price requires a date")
    # Validate source IDs everywhere, including field-level evidence and prices.
    def sources_walk(value, context):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "sourceIds":
                    for sid in child:
                        require(sid in maps["sources"], context + ": unknown source " + sid)
                elif key == "fieldSources":
                    for refs in child.values():
                        for sid in refs:
                            require(sid in maps["sources"], context + ": unknown field source " + sid)
                else:
                    sources_walk(child, context)
        elif isinstance(value, list):
            for child in value:
                sources_walk(child, context)
    for kind in ("brands", "products", "assets"):
        for record in data[kind]:
            sources_walk(record, record["id"])
    for product in data["products"]:
        visited, current = set(), product
        while current["relations"]["variantOf"] in maps["products"]:
            parent = current["relations"]["variantOf"]
            if parent in visited:
                errors.append(product["id"] + ": cyclic variant relation")
                break
            visited.add(parent)
            current = maps["products"][parent]
    for asset in data["assets"]:
        aid, rights, distribution = asset["id"], asset["rights"], asset["distribution"]
        require(Path(asset["fileName"]).name == asset["fileName"] and "\\" not in asset["fileName"], aid + ": filename must be a basename")
        for pid in asset["productIds"]:
            require(pid in maps["products"], aid + ": unknown product")
            if pid in maps["products"]:
                require(aid in maps["products"][pid]["mediaIds"], aid + ": product media reference missing")
        if distribution["status"] == "public":
            require(rights["status"] == "approved", aid + ": public image requires approved rights")
            require(rights["license"] in OPEN_MEDIA_LICENSES, aid + ": public image requires an explicit supported open license")
            require(bool(rights["holder"]) and bool(rights["evidenceUrl"]), aid + ": public image requires holder and permission evidence")
            relative = distribution["file"]
            require(bool(relative), aid + ": public image file missing")
            if relative:
                candidate = (root / relative).resolve()
                within = candidate.is_relative_to((root / "media/files").resolve()) and ".." not in Path(relative).parts
                require(within, aid + ": unsafe image path")
                if within:
                    require(candidate.is_file(), aid + ": image file missing")
                    if candidate.is_file():
                        require(sha(candidate.read_bytes()) == asset["sha256"], aid + ": image checksum mismatch")
                    public_files.add(candidate)
        else:
            require(distribution["file"] is None, aid + ": withheld media cannot include a file path")
    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif", ".heic"}
    for file in (root / "media").rglob("*"):
        if file.is_file() and file.suffix.lower() in image_extensions:
            require(file.resolve() in public_files, "Unapproved/unreferenced image binary: " + str(file.relative_to(root)))
    media_manifest = read(root / "media/manifest.json")
    require(sorted(media_manifest["metadataIds"]) == sorted(maps["assets"]), "Media manifest ID mismatch")
    if errors:
        raise CatalogError("\n".join(errors))
    data["stats"] = {"brands": len(data["brands"]), "products": len(data["products"]), "mediaMetadata": len(data["assets"]),
                     "publicImages": len(public_files), "verifiedProducts": sum(p["provenance"]["verification"] == "verified" for p in data["products"])}
    return data


def public_record(record, kind):
    value = copy.deepcopy(record)
    value["$schema"] = BASE_URL + "/schemas/" + kind + ".schema.json"
    return value


def ios_seed(data):
    brands = {b["id"]: b["name"] for b in data["brands"]}
    result = []
    for p in data["products"]:
        legacy = p["legacy"]
        price = next((x["amount"] for x in p["priceObservations"] if x["kind"] == "legacy-reference" and x["currency"] == "CNY"), None)
        result.append({"id": p["id"], "name": p["names"]["zh-CN"], "brand": brands[p["brandId"]], "model": p["model"], "series": p["series"],
                       "category": CATEGORIES[p["category"]], "variant": p["variant"]["label"], **p["specifications"], "color": p["variant"]["color"],
                       "suggestedUnitPriceCny": price, "imageKey": legacy["imageKey"], "popularity": legacy["popularity"], "tags": p["curation"]["tags"],
                       "revision": max(p["revision"], legacy["revision"]), "isActive": p["curation"]["listed"], "createdAt": legacy["createdAt"], "updatedAt": legacy["updatedAt"]})
    return {"version": data["manifest"]["catalogVersion"], "equipment": result}


def build(output, root=ROOT):
    data = validate(root)
    output = output.resolve()
    if output == root.resolve() or root.resolve().is_relative_to(output):
        raise CatalogError("Output cannot replace the source repository or an ancestor")
    if output.exists() and any(output.iterdir()) and not (output / ".badminton-db-build").is_file():
        raise CatalogError("Refusing to replace a non-build directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".badminton-db-", dir=output.parent))
    try:
        (stage / ".badminton-db-build").touch()
        (stage / ".nojekyll").touch()
        for schema in (root / "schemas").glob("*.json"):
            dest = stage / "schemas" / schema.name
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(schema, dest)
        for name in ("LICENSE", "LICENSE-DATA"):
            shutil.copy2(root / name, stage / name)
        products = [public_record(p, "product") for p in data["products"]]
        brands = [public_record(b, "brand") for b in data["brands"]]
        assets = [public_record(a, "asset") for a in data["assets"]]
        sources = [public_record(s, "source") for s in data["sources"]]
        for asset in assets:
            asset["downloadUrl"] = BASE_URL + "/" + asset["distribution"]["file"] if asset["distribution"]["status"] == "public" else None
            if asset["distribution"]["status"] == "public":
                relative = asset["distribution"]["file"]
                dest = stage / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / relative, dest)
        for product in products:
            write(stage / "v1/products" / (product["id"] + ".json"), product)
        summaries = [{k: p[k] for k in ("id", "slug", "brandId", "category", "names", "model", "mediaIds", "provenance")} for p in products]
        write(stage / "v1/products/index.json", {"dataVersion": data["manifest"]["dataVersion"], "products": summaries, "bySlug": {p["slug"]: p["id"] for p in products}})
        for brand in brands:
            write(stage / "v1/brands" / (brand["id"] + ".json"), {**brand, "productIds": [p["id"] for p in products if p["brandId"] == brand["id"]]})
        write(stage / "v1/brands/index.json", brands)
        for asset in assets:
            write(stage / "v1/media" / (asset["id"] + ".json"), asset)
        write(stage / "v1/media/index.json", {"metadata": assets, "publicImages": data["stats"]["publicImages"]})
        for source in sources:
            write(stage / "v1/sources" / (source["id"] + ".json"), source)
        write(stage / "v1/sources/index.json", sources)
        write(stage / "v1/categories/index.json", [{"id": k, "name": v, "productCount": sum(p["category"] == k for p in products)} for k, v in CATEGORIES.items()])
        brand_map = {b["id"]: b for b in brands}
        search = []
        for product in products:
            b = brand_map[product["brandId"]]
            terms = list(dict.fromkeys(x for x in [*product["names"].values(), product["model"], product["series"], *product["aliases"], b["name"], *b["aliases"]] if x))
            search.append({"id": product["id"], "slug": product["slug"], "brandId": product["brandId"], "category": product["category"], "terms": terms, "normalized": fold(" ".join(terms))})
        write(stage / "v1/search.json", search)
        aggregate = {"schemaVersion": 1, "dataVersion": data["manifest"]["dataVersion"], "brands": brands, "products": products, "media": assets, "sources": sources}
        write(stage / "v1/catalog.json", aggregate)
        (stage / "v1/catalog.json.gz").write_bytes(gzip.compress(encoded(aggregate), mtime=0))
        write(stage / "exports/ios/equipment_catalog.json", ios_seed(data))
        write(stage / "exports/ios/media-map.json", {"replaceExistingBundledImages": False, "assets": [{"legacyImageKeys": a["legacyImageKeys"], "mediaId": a["id"], "downloadUrl": a["downloadUrl"]} for a in assets]})
        write(stage / "v1/manifest.json", {"schemaVersion": 1, "dataVersion": data["manifest"]["dataVersion"], "catalogVersion": data["manifest"]["catalogVersion"], "updated": data["manifest"]["updated"],
            "counts": data["stats"], "catalog": "catalog.json", "products": "products/index.json", "brands": "brands/index.json", "media": "media/index.json", "sources": "sources/index.json", "search": "search.json", "checksums": "../checksums.json",
            "licenses": data["manifest"]["licenses"], "dataQuality": "Initial imported records are unverified; legacy prices are undated references, not current market prices."})
        write(stage / "index.json", {"project": "BadmintonDB", "repository": "https://github.com/Hessel2333/badminton-db", "api": "v1/manifest.json", "dataVersion": data["manifest"]["dataVersion"]})
        checksums = {str(p.relative_to(stage)): sha(p.read_bytes()) for p in sorted(stage.rglob("*")) if p.is_file() and not p.name.startswith(".")}
        write(stage / "checksums.json", checksums)
        if output.exists():
            shutil.rmtree(output)
        stage.rename(output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return data["stats"]


def package(output, root=ROOT):
    data = validate(root)
    dist = root / "dist"
    build(dist, root)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ("badminton-db-" + data["manifest"]["dataVersion"] + ".zip")
    stamp = tuple(map(int, data["manifest"]["updated"].split("-"))) + (0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted(dist.rglob("*")):
            if not file.is_file() or file.name == ".badminton-db-build":
                continue
            info = zipfile.ZipInfo(str(file.relative_to(dist)), date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, file.read_bytes(), compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise CatalogError("Release archive failed integrity check")
    (output / "SHA256SUMS").write_text(sha(archive.read_bytes()) + "  " + archive.name + "\n")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    b = sub.add_parser("build"); b.add_argument("--output", type=Path, default=ROOT / "dist")
    p = sub.add_parser("package"); p.add_argument("--output", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            print(json.dumps(validate()["stats"], ensure_ascii=False))
        elif args.command == "build":
            print(json.dumps(build(args.output), ensure_ascii=False))
        else:
            print(package(args.output))
    except (CatalogError, OSError, KeyError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
