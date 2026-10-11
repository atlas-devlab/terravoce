"""Read small native windows from public FAO COGs. Rasterio is only needed for capture."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import urllib.request
from urllib.parse import urlparse

import rasterio
from rasterio.windows import Window
from awash_irrigation import DATA, EVIDENCE, dekad, digest, protocol, read_json, verify_seal, write_new

HEADERS = {"User-Agent": "TerraVoceResearch/0.1 (public-data reproducibility)", "Accept": "application/json"}

def json_source(url, path):
    if path.exists():
        return read_json(path)
    if urlparse(url).netloc != "data.apps.fao.org":
        raise ValueError("Unexpected metadata publisher")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Metadata response exceeds bounded capture")
    value = json.loads(raw)
    if value["status"] != 200:
        raise ValueError("FAO metadata request unsuccessful")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return value

def capture(phase):
    p = protocol()
    if phase == "target":
        # The target is fetched only after replaying the persisted history-only prediction.
        verify_seal()
    elif (DATA / "target/manifest.json").exists():
        raise ValueError("Target already acquired; cannot reopen history capture")
    folder = DATA / phase
    if (folder / "manifest.json").exists():
        raise ValueError("Capture already sealed; use the offline replay")
    records = []
    periods = p["history"] if phase == "history" else [p["target"]]
    for metric, mapset_code in p["mapsets"].items():
        mapset_path = folder / f"{metric}-mapset.json"
        mapset = json_source(p["catalogBase"] + "/" + mapset_code, mapset_path)["response"]
        if mapset["code"] != mapset_code or mapset["measureUnit"] != p["unit"]:
            raise ValueError("Unexpected mapset identity or unit")
        for period_code in periods:
            raster_code = f"WAPOR-3.{mapset_code}.{period_code}"
            metadata_url = f"{p['catalogBase']}/{mapset_code}/rasters/{raster_code}"
            metadata_path = folder / f"{metric}-{period_code}.metadata.json"
            metadata = json_source(metadata_url, metadata_path)["response"]
            if metadata["code"] != raster_code or metadata["srs"]["epsg"] != "4326":
                raise ValueError("Unexpected raster identity or CRS")
            url = metadata["downloadUrl"]
            u = urlparse(url)
            expected_path = f"/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET/{mapset_code}/{raster_code}.tif"
            if u.scheme != "https" or u.netloc != "storage.googleapis.com" or u.path != expected_path or u.query:
                raise ValueError("Unexpected public FAO asset URL")
            extraction_path = folder / f"{metric}-{period_code}.pixels.json"
            if not extraction_path.exists():
                # Check range support before GDAL opens a multi-gigabyte continental asset.
                req = urllib.request.Request(url, headers={**HEADERS, "Range": "bytes=0-0"})
                with urllib.request.urlopen(req, timeout=25) as response:
                    if response.status != 206 or not response.headers.get("Content-Range", "").startswith("bytes 0-0/"):
                        raise ValueError("Asset does not support bounded range reads")
                    generation = response.headers["x-goog-generation"]
                    server_checksum = response.headers.get("x-goog-hash")
                    response.read(1)
                if not generation.isdigit():
                    raise ValueError("Missing immutable cloud asset generation")
                pinned_url = url + "?generation=" + generation
                xmin, ymin, xmax, ymax = p["bboxWgs84"]
                c, a, b, f, d, e = metadata["affineTransform"]
                col, row = math.floor((xmin-c)/a), math.floor((ymax-f)/e)
                width, height = math.ceil((xmax-c)/a)-col, math.ceil((ymin-f)/e)-row
                if b != 0 or d != 0 or a <= 0 or e >= 0 or not 0 < width*height <= 4096:
                    raise ValueError("Unbounded or unsupported raster window")
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="25",
                                  GDAL_HTTP_MAX_RETRY="1", GDAL_HTTP_USERAGENT=HEADERS["User-Agent"],
                                  CPL_VSIL_CURL_CACHE_SIZE="8388608"):
                    with rasterio.open(pinned_url) as raster:
                        if (raster.crs.to_epsg() != 4326 or list(raster.transform.to_gdal()) != metadata["affineTransform"]
                            or raster.nodata != metadata["noDataValue"] or raster.count != 1
                            or raster.scales[0] != metadata["scale"] or raster.offsets[0] != metadata["offset"]):
                            raise ValueError("Raster header does not match FAO metadata")
                        values = raster.read(1, window=Window(col, row, width, height)).tolist()
                clip = {"version": "fao-native-pixel-window-v1", "rasterCode": raster_code,
                        "period": dekad(period_code), "unit": metadata["measureUnit"], "scale": metadata["scale"],
                        "offset": metadata["offset"], "noDataValue": metadata["noDataValue"], "crs": "EPSG:4326",
                        "affineTransform": metadata["affineTransform"],
                        "window": {"col": col, "row": row, "width": width, "height": height}, "values": values,
                        "source": {"metadataUrl": metadata_url, "downloadUrl": url, "generation": generation,
                                   "pinnedRangeReadUrl": pinned_url, "serverChecksum": server_checksum,
                                   "archiveScope": "native pixel window, not a complete copy/hash of the original GeoTIFF"}}
                write_new(extraction_path, clip)
            entry = {"metric": metric, "period": period_code}
            for role, path in (("mapset", mapset_path), ("metadata", metadata_path), ("extraction", extraction_path)):
                entry[role + "Path"], entry[role + "Hash"] = path.name, digest(path.read_bytes())
            records.append(entry)
    manifest = {"version": "awash-pinned-native-windows-v1", "phase": phase,
                "protocolHash": digest((DATA / "protocol.json").read_bytes()),
                "capturedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "records": records, "fullOriginalRasterArchived": False,
                "license": "FAO WaPOR attribution; source-specific mapset license retained in raw metadata",
                "captureLibrary": {"rasterio": rasterio.__version__, "gdal": rasterio.__gdal_version__}}
    if phase == "target":
        manifest["predictionHashBeforeAcquisition"] = digest((EVIDENCE / "prediction.json").read_bytes())
    write_new(folder / "manifest.json", manifest)
    print(json.dumps({"phase": phase, "nativeWindows": len(records), "manifest": str(folder / "manifest.json")}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["history", "target"])
    capture(parser.parse_args().phase)
