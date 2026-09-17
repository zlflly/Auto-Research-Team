#!/usr/bin/env python3
"""Non-destructive local installer. Dry-run by default; Python >=3.11."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NAME = "auto-research-team"
SKILL = "auto-research"

class InstallError(Exception):
    pass

def files(root: Path) -> dict[str, str]:
    result = {}
    for p in sorted(root.rglob("*")):
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        if p.is_symlink():
            raise InstallError(f"Refusing a symlink in package/install path: {p}")
        if p.is_file():
            result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def safe_target(repo: Path, relative: str) -> Path:
    target = repo / relative
    for p in [target, *target.parents]:
        if p == repo.parent:
            break
        if p.is_symlink():
            raise InstallError(f"Refusing symlink target: {p}")
    if not target.resolve().is_relative_to(repo):
        raise InstallError("Installation path escapes the project.")
    return target

def plan_install(repo: Path, skill_only: bool = False, package_root: Path = PACKAGE_ROOT) -> dict:
    if repo.is_symlink():
        raise InstallError("Pass the actual project path, not a symlink.")
    repo = repo.resolve()
    if not repo.is_dir():
        raise InstallError("--repo must name an existing project directory.")
    plugin_src = package_root / "plugins" / NAME
    plugin_dest = safe_target(repo, f"plugins/{NAME}")
    skill_dest = safe_target(repo, f".agents/skills/{SKILL}")
    if skill_only:
        source, destination = plugin_src / "skills" / SKILL, skill_dest
        if plugin_dest.exists():
            raise InstallError("Plugin copy already exists; do not install a duplicate standalone skill.")
    else:
        source, destination = plugin_src, plugin_dest
        if skill_dest.exists():
            raise InstallError("Standalone skill already exists; remove/migrate it explicitly before plugin installation.")
    source_files = files(source)
    if not source_files:
        raise InstallError("Source package is missing or empty.")
    copy_needed = not destination.exists()
    if destination.exists() and (not destination.is_dir() or files(destination) != source_files):
        raise InstallError(f"Different content already exists at {destination}; back it up and migrate explicitly.")
    writes: list[tuple[Path, str]] = []
    catalog_name = None
    if not skill_only:
        market = safe_target(repo, ".agents/plugins/marketplace.json")
        if market.exists():
            try:
                catalog = json.loads(market.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise InstallError(f"Cannot parse existing marketplace: {exc}") from exc
            if not isinstance(catalog, dict) or not isinstance(catalog.get("plugins"), list):
                raise InstallError("Existing marketplace has an unsupported shape; not overwriting it.")
        else:
            catalog = {"name":"personal-research", "interface":{"displayName":"Personal Research"}, "plugins":[]}
        catalog_name = catalog.get("name")
        if not isinstance(catalog_name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", catalog_name):
            raise InstallError("Marketplace name is missing or cannot safely be used as a config key.")
        if any(not isinstance(x, dict) for x in catalog["plugins"]):
            raise InstallError("Existing marketplace entries are not objects.")
        matches = [x for x in catalog["plugins"] if x.get("name") == NAME]
        expected_source = {"source":"local", "path":f"./plugins/{NAME}"}
        if len(matches) > 1 or (matches and matches[0].get("source") != expected_source):
            raise InstallError("A conflicting marketplace entry already uses this plugin name.")
        if not matches:
            catalog["plugins"].append({"name":NAME,"source":expected_source,
                "policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"})
            writes.append((market, json.dumps(catalog, indent=2, ensure_ascii=False)+"\n"))
        config = safe_target(repo, ".codex/config.toml")
        text = config.read_text(encoding="utf-8") if config.exists() else ""
        try:
            cfg = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise InstallError(f"Existing config is invalid TOML; not editing it: {exc}") from exc
        key = f"{NAME}@{catalog_name}"
        plugins = cfg.get("plugins", {})
        if not isinstance(plugins, dict):
            raise InstallError("Existing [plugins] value has an unsupported shape.")
        existing = plugins.get(key)
        if existing is not None:
            if not isinstance(existing, dict) or existing.get("enabled") is not True:
                raise InstallError("Plugin has existing disabled/custom configuration; enable it explicitly instead of overwriting.")
        else:
            addition = f'\n# AutoResearch Team local plugin\n[plugins."{key}"]\nenabled = true\n'
            candidate = text.rstrip()+"\n"+addition if text.strip() else addition.lstrip()
            # Catch conflicts with inline/sealed TOML tables before any filesystem write.
            try:
                tomllib.loads(candidate)
            except tomllib.TOMLDecodeError as exc:
                raise InstallError(f"Cannot append plugin configuration safely: {exc}") from exc
            writes.append((config, candidate))
    return {"repo":repo,"source":source,"destination":destination,"copy_needed":copy_needed,
            "writes":writes,"marketplace":catalog_name,"skill_only":skill_only}

def apply_plan(plan: dict) -> None:
    # All semantic conflict checks happen in plan_install before the first write.
    # This is not a multi-file transaction; backups support recovery after I/O failure.
    if plan["copy_needed"]:
        shutil.copytree(plan["source"], plan["destination"],
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for path, text in plan["writes"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(path, path.with_name(path.name+f".backup-{suffix}"))
        tmp = path.with_name(path.name+".autoresearch.tmp")
        if tmp.exists():
            raise InstallError(f"Temporary file already exists: {tmp}")
        with tmp.open("x", encoding="utf-8") as f:
            f.write(text)
        tmp.replace(path)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skill-only", action="store_true")
    args = parser.parse_args()
    try:
        plan = plan_install(args.repo, args.skill_only)
        out = {"mode":"apply" if args.apply else "dry-run", "destination":str(plan["destination"]),
               "copy_needed":plan["copy_needed"],"config_writes":[str(p) for p,_ in plan["writes"]],
               "marketplace":plan["marketplace"]}
        if args.apply:
            apply_plan(plan)
            out["result"] = "Local files prepared; host discovery/installation and native-subagent testing still required."
        else:
            out["result"] = "No files changed. Re-run with --apply to prepare local installation."
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    except (InstallError, OSError, ValueError) as exc:
        print(f"Installation refused: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
