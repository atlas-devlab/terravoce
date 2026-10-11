"""Launch real AEA/Tendermint replicas and inject complete node outages."""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import urllib.request
import yaml

ROOT = Path(__file__).resolve().parent
TM_IMAGE = "valory/open-autonomy-tendermint@sha256:e2e1a4274ef9878137a28f20c4e9895b3c5dd6c1c0165fcf9db5b654b6f7d746"


def run(*args, cwd=None, capture=False):
    return subprocess.run(list(args), cwd=cwd, check=True, text=True, encoding="utf8",
                          stdout=subprocess.PIPE if capture else None).stdout


def status(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as response:
            return json.load(response)["result"]
    except (OSError, ValueError, KeyError):
        return None


def scenario(shared, offline, timeout):
    name = f"offline-{offline}"
    folder = shared / name
    if folder.exists():
        raise ValueError(f"Scenario already exists: {folder}; use a new run folder")
    folder.mkdir()
    nodes = folder / "nodes"
    nodes.mkdir()
    job = json.loads((shared / "job.json").read_text())
    shutil.copy(shared / "job.json", folder / "job.json")
    shutil.copy(shared / "fixture.json", folder / "fixture.json")
    # Genesis has all four validators with equal power, even when nodes later stop.
    run("docker", "run", "--rm", "--mount", f"type=bind,source={nodes},target=/tendermint",
        "--entrypoint", "/usr/bin/tendermint", TM_IMAGE, "testnet", "--v", "4", "--o", "/tendermint")
    peer_ids = []
    for i in range(4):
        node_key = json.loads((nodes / f"node{i}/config/node_key.json").read_text())
        public_key = base64.b64decode(node_key["priv_key"]["value"])[32:]
        peer_ids.append(hashlib.sha256(public_key).hexdigest()[:40])
    services = {}
    configs = list(yaml.safe_load_all((ROOT / ".runtime/agent/aea-config.yaml").read_text()))
    for i in range(4):
        config = deepcopy(configs)
        params = config[2]["models"]["params"]["args"]
        params.update(oracle_url=f"http://oracle{i}:3000", tendermint_url=f"http://tm{i}:26657",
                      tendermint_com_url=f"http://tm{i}:8080", tendermint_p2p_url=f"tm{i}:26656")
        params["setup"].update(all_participants=job["operators"], participants=job["operators"], consensus_threshold=3)
        (folder / f"agent{i}.yaml").write_text(yaml.safe_dump_all(config, sort_keys=False))
        (folder / f"out{i}").mkdir()
        config_path = nodes / f"node{i}/config/config.toml"
        text = config_path.read_text(encoding="utf8")
        peers = ",".join(f"{peer_ids[j]}@tm{j}:26656" for j in range(4) if j != i)
        text = re.sub(r'(?m)^persistent_peers = .*$', f'persistent_peers = "{peers}"', text)
        text = text.replace('addr_book_strict = true', 'addr_book_strict = false')
        text = text.replace('allow_duplicate_ip = false', 'allow_duplicate_ip = true')
        text = text.replace('laddr = "tcp://127.0.0.1:26657"', 'laddr = "tcp://0.0.0.0:26657"')
        config_path.write_text(text, encoding="utf8")
        common = {"restart": "no", "logging": {"driver": "json-file", "options": {"max-size": "5m", "max-file": "2"}}}
        services[f"oracle{i}"] = {**common, "image": "terravoce-oracle:local", "volumes": [f"{folder.as_posix()}:/job:ro"]}
        services[f"agent{i}"] = {**common, "image": "terravoce-autonomy:local", "volumes": [
            f"{(folder / f'agent{i}.yaml').as_posix()}:/agent/aea-config.yaml:ro",
            f"{folder.as_posix()}:/job:ro", f"{(shared / f'keys{i}').as_posix()}:/keys:ro",
            f"{(folder / f'out{i}').as_posix()}:/out"], "depends_on": [f"oracle{i}"]}
        services[f"tm{i}"] = {**common, "image": TM_IMAGE, "environment": {
            "ID": str(i), "PROXY_APP": f"tcp://agent{i}:26658", "TMHOME": f"/tendermint/node{i}",
            "CREATE_EMPTY_BLOCKS": "true", "USE_GRPC": "false", "DEV_MODE": "0",
            "LOG_FILE": "/tmp/tendermint.log", "LOG_LEVEL": "info", "WRITE_TO_LOG": "false"},
            "volumes": [f"{nodes.as_posix()}:/tendermint"], "ports": [f"127.0.0.1:{27657+i}:26657"],
            "networks": {"default": {"aliases": [f"node{i}"]}},
            "depends_on": [f"agent{i}"]}
    (folder / "compose.yaml").write_text(yaml.safe_dump({"name": "terravoce-" + name, "services": services}, sort_keys=False))
    compose = ["docker", "compose", "-f", str(folder / "compose.yaml")]
    report = {"offline": offline, "quorum": 3, "validators": 4}
    try:
        run(*compose, "up", "-d")
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            raw_states = run(*compose, "ps", "-a", "--format", "json", capture=True)
            states = [json.loads(line) for line in raw_states.splitlines() if line.strip()]
            if any(s.get("State") == "exited" for s in states):
                raise RuntimeError("A replica exited during startup; see cluster.log")
            statuses = [status(27657+i) for i in range(4)]
            if all(s and int(s["sync_info"]["latest_block_height"]) >= 2 for s in statuses):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Four ABCI/Tendermint replicas did not become ready")
        report["heightsBefore"] = [s["sync_info"]["latest_block_height"] for s in statuses]
        stopped = list(range(4-offline, 4))
        run(*compose, "stop", "-t", "2", *[f"{service}{i}" for i in stopped for service in ("agent", "tm", "oracle")])
        report["stoppedNodes"] = stopped
        time.sleep(3)
        report["heightsAfterStop"] = [(status(27657+i) or {}).get("sync_info", {}).get("latest_block_height") for i in range(4-offline)]
        (folder / "start").touch()
        deadline = time.monotonic() + timeout
        certificate = None
        while time.monotonic() < deadline:
            for i in range(4-offline):
                path = folder / f"out{i}/certificate.json"
                if path.exists():
                    try:
                        certificate = json.loads(path.read_text(encoding="utf8"))
                    except (PermissionError, json.JSONDecodeError):
                        # Windows bind mounts can briefly lock the atomic rename.
                        continue
                    break
            if certificate:
                break
            time.sleep(1)
        report["certificate"] = certificate
        report["heightsAfter"] = [(status(27657+i) or {}).get("sync_info", {}).get("latest_block_height") for i in range(4)]
        states = [json.loads(line) for line in run(*compose, "ps", "-a", "--format", "json", capture=True).splitlines() if line.strip()]
        for i in range(4-offline):
            if not any(s.get("Service") == f"agent{i}" and s.get("State") == "running" for s in states):
                raise AssertionError(f"Surviving agent {i} crashed; absence of a certificate is not a quorum test")
        if offline == 2:
            if report["heightsAfter"][:2] != report["heightsAfterStop"]:
                raise AssertionError("Consensus advanced with two of four validators offline")
        if (offline <= 1) != bool(certificate):
            raise AssertionError(f"Unexpected certificate with {offline} nodes offline")
        print(json.dumps({"scenario": name, "certificate": bool(certificate), "heights": report["heightsAfter"]}), flush=True)
        return report
    except Exception:
        report["error"] = traceback.format_exc()
        raise
    finally:
        logs = run(*compose, "logs", "--no-color", capture=True)
        (folder / "cluster.log").write_text(logs, encoding="utf8")
        run(*compose, "down", "-t", "2")
        (folder / "report.json").write_text(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_folder", type=Path)
    args = parser.parse_args()
    shared = args.run_folder.resolve()
    reports = [scenario(shared, 2, 25), scenario(shared, 1, 120)]
    (shared / "cluster-results.json").write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
