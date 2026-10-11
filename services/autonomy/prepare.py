"""Prepare a pinned Open Autonomy AEA runtime. Run from the repository root."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import yaml
from aea.cli.fingerprint import fingerprint_package

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
AUTONOMY_COMMIT = "62033a2b371d2be43c25abf800f206b2f679aca2"
AEA_COMMIT = "5c2d4b9cb9c2336835dbdde551d79aae7aa99686"


def upstream(name, url, commit, supplied):
    path = Path(supplied).resolve() if supplied else RUNTIME / "upstream" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", url, str(path)], check=True)
        subprocess.run(["git", "checkout", commit], cwd=path, check=True)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    if actual != commit:
        raise ValueError(f"Unpinned {name}: {actual}")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--autonomy-source")
    parser.add_argument("--aea-source")
    args = parser.parse_args()
    oa = upstream("open-autonomy", "https://github.com/valory-xyz/open-autonomy.git", AUTONOMY_COMMIT, args.autonomy_source)
    aea = upstream("open-aea", "https://github.com/valory-xyz/open-aea.git", AEA_COMMIT, args.aea_source)
    registry = RUNTIME / "registry"
    # Copy each package from one revision; never merge two versions of a package.
    for generated in [registry, RUNTIME / "agent/vendor"]:
        if generated.exists():
            generated.resolve().relative_to(RUNTIME.resolve())
            shutil.rmtree(generated)
    shutil.copytree(aea / "packages", registry)
    for author in (oa / "packages").iterdir():
        if not author.is_dir():
            continue
        for kind in author.iterdir():
            if not kind.is_dir():
                continue
            for package in kind.iterdir():
                if not package.is_dir():
                    continue
                target = registry / author.name / kind.name / package.name
                if target.exists():
                    target.resolve().relative_to(registry.resolve())
                    shutil.rmtree(target)
                shutil.copytree(package, target)
    # Restore Git's canonical LF bytes after a Windows autocrlf checkout.
    for path in registry.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            if b"\0" not in data:
                try:
                    data.decode("utf8")
                except UnicodeDecodeError:
                    continue
                path.write_bytes(data.replace(b"\r\n", b"\n"))
    # Build the custom skill configuration using the pinned upstream parameter schema.
    skill = yaml.safe_load((oa / "packages/valory/skills/register_reset_abci/skill.yaml").read_text())
    skill.update(name="oracle_abci", author="terravoce", description="Independent Oracle evaluation and 3-of-4 action certification",
                 fingerprint={}, skills=[yaml.safe_load((oa / "packages/valory/agents/register_reset/aea-config.yaml").read_text().split("---")[0])["skills"][1]])
    skill["behaviours"]["main"]["class_name"] = "OracleRoundBehaviour"
    params = skill["models"]["params"]["args"]
    params.update(service_id="terravoce_oracle", round_timeout_seconds=60.0,
                  oracle_url="http://oracle0:3000", oracle_token="local-fixture-oracle",
                  job_path="/job/job.json", certificate_path="/out/certificate.json")
    source_skill = ROOT / "packages/terravoce/skills/oracle_abci"
    (source_skill / "skill.yaml").write_text(yaml.safe_dump(skill, sort_keys=False))
    fingerprint_package(source_skill, "skill")
    agent = RUNTIME / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_skill, agent / "skills/oracle_abci", dirs_exist_ok=True)
    config_docs = list(yaml.safe_load_all((oa / "packages/valory/agents/register_reset/aea-config.yaml").read_text()))
    config = config_docs[0]
    config.update(agent_name="terravoce_oracle", author="terravoce", description="TerraVoce 3-of-4 Oracle bridge", fingerprint={})
    config["skills"] = [s for s in config["skills"] if "/abstract_" in s] + ["terravoce/oracle_abci:0.1.0"]
    # Include the full dependency closure needed by abstract_round_abci.
    abstract = yaml.safe_load((oa / "packages/valory/skills/abstract_round_abci/skill.yaml").read_text())
    config["protocols"] = abstract["protocols"]
    config["contracts"] = abstract["contracts"]
    queue = [(kind, public_id) for kind in ("connections", "contracts", "protocols", "skills")
             for public_id in config[kind] if not public_id.startswith("terravoce/")]
    seen = set()
    filenames = {"connections": "connection.yaml", "contracts": "contract.yaml",
                 "protocols": "protocol.yaml", "skills": "skill.yaml"}
    while queue:
        kind, public_id = queue.pop()
        author, name = public_id.split(":")[0].split("/")
        identity = (kind, author, name)
        if identity in seen:
            continue
        seen.add(identity)
        package = registry / author / kind / name
        shutil.copytree(package, agent / "vendor" / author / kind / name)
        package_config = yaml.safe_load((package / filenames[kind]).read_text(encoding="utf8"))
        for dep_kind in filenames:
            for dep in package_config.get(dep_kind, []):
                queue.append((dep_kind, dep))
                if not any(existing.split(":")[0] == dep.split(":")[0] for existing in config[dep_kind]):
                    config[dep_kind].append(dep)
    config["private_key_paths"] = {"ethereum": "/keys/ethereum_private_key.txt"}
    config["default_connection"] = "valory/http_client:0.23.0"
    config["default_routing"] = {"valory/abci:0.1.0": "valory/abci:0.1.0",
                                 "valory/http:1.0.0": "valory/http_client:0.23.0"}
    docs = [config, {"public_id": "valory/abci:0.1.0", "type": "connection", "config": {
        "target_skill_id": "terravoce/oracle_abci:0.1.0", "host": "0.0.0.0", "port": 26658,
        "use_tendermint": False}}, {"public_id": "terravoce/oracle_abci:0.1.0", "type": "skill",
        "models": {"params": {"args": params}}},
        {"public_id": "valory/p2p_libp2p_client:0.1.0", "type": "connection",
         "config": {"nodes": [{"uri": "localhost:11000", "public_key": "03c74dbfbe7bbc1b42429f78778017a3cd7eaf9d59d1634c9505a3f7c1a9350e71"}]},
         "cert_requests": [{"identifier": "acn", "ledger_id": "ethereum", "message_format": "{public_key}",
                            "not_before": "2026-01-01", "not_after": "2036-01-01",
                            "public_key": "03c74dbfbe7bbc1b42429f78778017a3cd7eaf9d59d1634c9505a3f7c1a9350e71",
                            "save_path": ".certs/local-unused-acn.txt"}]}]
    (agent / "aea-config.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False))
    shutil.copyfile(oa / "LICENSE", agent / "OPEN_AUTONOMY_LICENSE")
    shutil.copyfile(aea / "LICENSE", agent / "OPEN_AEA_LICENSE")
    shutil.copyfile(ROOT / "NOTICE", agent / "NOTICE")
    (RUNTIME / "provenance.json").write_text(json.dumps({"open-autonomy": AUTONOMY_COMMIT, "open-aea": AEA_COMMIT}, indent=2))
    print("Prepared pinned runtime at", agent)


if __name__ == "__main__":
    main()
