import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def run_cmd(cmd, cwd, log_path):
    start = utc_now()
    with open(log_path, "w", encoding="ascii", errors="replace") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        exit_code = proc.wait()
    finish = utc_now()
    return exit_code, start, finish


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_paths(base: Path, items):
    return [str((base / p).resolve()) for p in items]


def git_clone_at(repo_url: str, sha: str, checkout_dir: Path) -> None:
    if checkout_dir.exists():
        shutil.rmtree(checkout_dir)
    ensure_dir(checkout_dir)
    subprocess.check_call(["git", "clone", "--no-checkout", repo_url, str(checkout_dir)])
    subprocess.check_call(["git", "-C", str(checkout_dir), "checkout", sha])


def verilator_base_cmd(stage, repo_dir: Path):
    sources = stage.get("sources", [])
    include_dirs = stage.get("include_dirs", [])
    defines = stage.get("defines", [])
    flags = stage.get("flags", [])

    cmd = ["verilator"]
    for inc in include_dirs:
        cmd.append(f"-I{inc}")
    for d in defines:
        cmd.append(f"-D{d}")
    cmd.extend(flags)
    cmd.extend(resolve_paths(repo_dir, sources))
    return cmd


def run_lint(stage, repo_dir: Path, stage_dir: Path):
    cmd = verilator_base_cmd(stage, repo_dir)
    cmd.insert(1, "--lint-only")
    log_path = stage_dir / "lint.log"
    return cmd, log_path


def run_build(stage, repo_dir: Path, stage_dir: Path, jobs: int):
    cmd = verilator_base_cmd(stage, repo_dir)
    mode_flags = {
        "--binary",
        "--cc",
        "--sc",
        "--dpi-hdr-only",
        "--lint-only",
        "--xml-only",
        "--json-only",
        "--E",
    }
    top = stage.get("top")
    if top:
        cmd.extend(["--top-module", top])

    mdir = (stage_dir / "obj_dir").resolve()
    ensure_dir(mdir)
    cmd.extend(["--Mdir", str(mdir)])

    exe = stage.get("exe", [])
    if exe:
        if not any(flag in mode_flags for flag in stage.get("flags", [])):
            cmd.insert(1, "--cc")
        cmd.extend(["--exe"] + resolve_paths(repo_dir, exe))
    elif not any(flag in mode_flags for flag in stage.get("flags", [])):
        cmd.insert(1, "--binary")
    cmd.append("--build")
    if jobs:
        cmd.extend(["-j", str(jobs)])

    log_path = stage_dir / "build.log"
    binary = None
    if top:
        binary = str((mdir / f"V{top}").resolve())
    return cmd, log_path, binary


def run_sim(stage, repo_dir: Path, stage_dir: Path, build_binary: str | None):
    binary = stage.get("binary")
    if binary:
        binary_path = (repo_dir / binary).resolve()
    elif build_binary:
        binary_path = Path(build_binary)
    else:
        raise ValueError("sim stage requires 'binary' or build stage with top")

    args = stage.get("args", [])
    cmd = [str(binary_path)] + args
    log_path = stage_dir / "sim.log"
    return cmd, log_path, str(binary_path)


def load_plan(plan_path: Path) -> dict:
    with open(plan_path, "r", encoding="ascii") as handle:
        return json.load(handle)


def write_results(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="ascii") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def run_plan(repo_url: str, sha: str, plan_path: Path, out_dir: Path, jobs: int) -> int:
    run_id = str(uuid.uuid4())
    ensure_dir(out_dir)

    checkout_dir = out_dir / "checkout"
    artifacts_dir = out_dir / "artifacts"
    ensure_dir(artifacts_dir)

    git_clone_at(repo_url, sha, checkout_dir)
    plan = load_plan(plan_path)

    stages = []
    overall_status = "passed"
    build_binary = None

    started_at = utc_now()

    for stage in plan.get("stages", []):
        name = stage.get("name", stage.get("type", "stage"))
        stage_type = stage.get("type")
        stage_dir = artifacts_dir / name
        ensure_dir(stage_dir)

        result = {
            "name": name,
            "type": stage_type,
            "status": "skipped",
            "started_at": None,
            "finished_at": None,
            "exit_code": 0,
            "log": "",
        }

        try:
            if stage_type == "lint":
                cmd, log_path = run_lint(stage, checkout_dir, stage_dir)
            elif stage_type == "build":
                cmd, log_path, binary = run_build(stage, checkout_dir, stage_dir, jobs)
                if binary:
                    build_binary = binary
                    result["binary"] = binary
            elif stage_type == "sim":
                cmd, log_path, binary = run_sim(stage, checkout_dir, stage_dir, build_binary)
                result["binary"] = binary
            else:
                raise ValueError(f"unknown stage type: {stage_type}")

            exit_code, start, finish = run_cmd(cmd, cwd=checkout_dir, log_path=log_path)
            if stage_type == "sim":
                pass_regex = stage.get("pass_regex")
                fail_regex = stage.get("fail_regex")
                if pass_regex or fail_regex:
                    with open(log_path, "r", encoding="ascii", errors="replace") as handle:
                        log_text = handle.read()
                    if fail_regex and re.search(fail_regex, log_text):
                        exit_code = 1
                        result["failure_reason"] = f"fail_regex matched: {fail_regex}"
                    elif pass_regex and not re.search(pass_regex, log_text):
                        exit_code = 1
                        result["failure_reason"] = f"pass_regex not matched: {pass_regex}"
            result.update(
                {
                    "status": "passed" if exit_code == 0 else "failed",
                    "started_at": start,
                    "finished_at": finish,
                    "exit_code": exit_code,
                    "log": str(log_path.resolve()),
                }
            )

            if exit_code != 0:
                overall_status = "failed"
                stages.append(result)
                break
        except Exception as exc:  # noqa: BLE001
            result.update(
                {
                    "status": "failed",
                    "started_at": result["started_at"] or utc_now(),
                    "finished_at": utc_now(),
                    "exit_code": 1,
                    "log": str((stage_dir / "error.log").resolve()),
                }
            )
            with open(result["log"], "w", encoding="ascii", errors="replace") as handle:
                handle.write(str(exc))
            overall_status = "failed"
            stages.append(result)
            break

        stages.append(result)

    finished_at = utc_now()
    results = {
        "run_id": run_id,
        "repo": repo_url,
        "sha": sha,
        "plan": str(plan_path.resolve()),
        "started_at": started_at,
        "finished_at": finished_at,
        "status": overall_status,
        "artifacts_dir": str(artifacts_dir.resolve()),
        "checkout_dir": str(checkout_dir.resolve()),
        "stages": stages,
    }

    write_results(out_dir / "results.json", results)
    return 0 if overall_status == "passed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hwci")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a plan against a repo at a specific SHA")
    run_parser.add_argument("--repo", required=True, help="Git repo URL")
    run_parser.add_argument("--sha", required=True, help="Git commit SHA")
    run_parser.add_argument("--plan", required=True, help="Path to plan.json")
    run_parser.add_argument("--out", required=True, help="Output directory")
    run_parser.add_argument("--jobs", type=int, default=0, help="Parallel jobs for Verilator build")

    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 2

    out_dir = Path(args.out)
    plan_path = Path(args.plan)
    return run_plan(args.repo, args.sha, plan_path, out_dir, args.jobs)


if __name__ == "__main__":
    sys.exit(main())
