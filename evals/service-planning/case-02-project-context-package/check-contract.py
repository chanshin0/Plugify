#!/usr/bin/env python3
"""Deterministic regression checks for project-context package validation."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
CASE_DIR = Path(__file__).resolve().parent
REQUEST = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else CASE_DIR / "fixture/REQUEST.md"
)
VALIDATOR = REPO / "skills/service-planning/scripts/validate-project-context.py"
REFERENCE = REPO / "skills/service-planning/references/project-context-package.md"
REPORT_ASSET = REPO / "skills/service-planning/assets/DELIVERY-REPORT.md"
SKILL = REPO / "skills/service-planning/SKILL.md"
BUILDER = REPO / "skills/service-planning/agents/context-package-builder.md"
SYSTEM = REPO / "SYSTEM.md"
PROMPTS = [
    "00-ORCHESTRATOR.md",
    "10-BUSINESS-DISCOVERY.md",
    "20-SOURCE-CARTOGRAPHER.md",
    "30-WORKFLOW-MODELER.md",
    "40-DATA-ARCHITECT.md",
    "50-PORTAL-PLANNER.md",
    "60-MIGRATION-PLANNER.md",
    "70-SECURITY-AI-REVIEWER.md",
    "90-COMPLETENESS-CRITIC.md",
]
HEADINGS = [
    "## 역할",
    "## 필수 읽기",
    "## 호출 입력",
    "## 수행",
    "## 안전·금지 경계",
    "## 산출물",
    "## 완료 검증",
    "## 중단·질문 조건",
]
TESTS = [
    "explicit_legacy_request_contract",
    "valid_legacy_package",
    "missing_prompt_rejected",
    "missing_prompt_heading_rejected",
    "fenced_heading_rejected",
    "orchestrator_route_gap_rejected",
    "commented_route_rejected",
    "stale_actual_tree_rejected",
    "fenced_tree_rejected",
    "long_fence_rejected",
    "trailing_text_fence_rejected",
    "raw_html_structure_rejected",
    "processing_instruction_structure_rejected",
    "flattened_tree_rejected",
    "legacy_discovery_gap_rejected",
    "conflicting_profile_rejected",
    "invalid_profile_rejected",
    "valid_nonlegacy_package",
    "shipped_contract_assets",
]
ROLE_PURPOSES = {
    "00-ORCHESTRATOR.md": "Route stage-aware work to one owner per artifact and verify actual outputs.",
    "10-BUSINESS-DISCOVERY.md": "Discover actual staff work, frequency, exceptions, and shadow work without inventing architecture.",
    "20-SOURCE-CARTOGRAPHER.md": "Map only approved local source structure while keeping runtime use unknown.",
    "30-WORKFLOW-MODELER.md": "Model one evidenced workflow from trigger through exception, recovery, and outcome.",
    "40-DATA-ARCHITECT.md": "Design a logical target model, crosswalk, projections, and authority states after discovery gates.",
    "50-PORTAL-PLANNER.md": "Translate evidenced staff roles and workflow into an internal work-hub and five UI states.",
    "60-MIGRATION-PLANNER.md": "Plan shadow, validation, read canary, rollback, and later authority gates without executing them.",
    "70-SECURITY-AI-REVIEWER.md": "Review role, data class, action, projection, audit, and read-only agent boundaries.",
    "90-COMPLETENESS-CRITIC.md": "Blindly find missing evidence, premature gates, prompt gaps, and report-tree mismatch.",
}


def render_tree(root: Path) -> str:
    lines = [f"{root.name}/"]

    def walk(directory: Path, prefix: str) -> None:
        entries = sorted(directory.iterdir(), key=lambda path: (path.is_file(), path.name))
        for index, entry in enumerate(entries):
            last = index == len(entries) - 1
            connector = "└── " if last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                walk(entry, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)


def write_report(root: Path, tree_override: str | None = None) -> None:
    report = root / "DELIVERY-REPORT.md"
    report.write_text("placeholder", encoding="utf-8")
    tree = tree_override or render_tree(root)
    profile = (
        "legacy-modernization"
        if (root / "BUSINESS-CAPABILITY-MAP.md").is_file()
        else "persistent-context"
    )
    report.write_text(
        f"# 결과 보고\n\n> profile: {profile}\n\n"
        "## 결과와 현재 gate\n\nvalidated result\n\n"
        "## 사실·가정·미확인\n\nevidence boundary\n\n"
        "## 핵심 결정과 중단선\n\nstop boundary\n\n"
        "## 검증\n\nvalidator evidence\n\n"
        "## 실제 디렉터리 구조\n\n```text\n"
        + tree
        + "\n```\n\n"
        "## 재진입 경로\n\nREADME then STATUS\n\n"
        "## 다음 gate\n\nclosing evidence\n\n"
        "## 유보·승인 필요\n\nexecution approval\n",
        encoding="utf-8",
    )


def make_package(root: Path, legacy: bool) -> None:
    root.mkdir(parents=True)
    for name in ["README.md", "STATUS.md", "기획서.md", "gaps.md"]:
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    if legacy:
        for name in [
            "BUSINESS-CAPABILITY-MAP.md",
            "PROCESS-CATALOG.md",
            "M0A-DISCOVERY-GUIDE.md",
        ]:
            (root / name).write_text(f"# {name}\n", encoding="utf-8")
    prompt_dir = root / "prompts"
    prompt_dir.mkdir()
    for name in PROMPTS:
        purpose = ROLE_PURPOSES[name]
        body = [
            f"# {name}",
            f"## 역할\n\n{purpose} This role does not own decisions outside that result.",
            "## 필수 읽기\n\nRead repository rules, package README, STATUS, and only the canonical evidence needed for this role.",
            "## 호출 입력\n\n- TASK: one bounded outcome\n- TARGETS: allowed read/write paths\n- OUTPUT: one owned artifact\n- EVIDENCE: confirmed facts and states\n- APPROVALS: existing authority or none",
            f"## 수행\n\nExecute the project-specific responsibility: {purpose}",
            "## 안전·금지 경계\n\nDo not access servers, operational data, or external APIs without approval; static source never proves actual use.",
            "## 산출물\n\nWrite only the declared OUTPUT and preserve every other agent or user-owned artifact.",
            "## 완료 검증\n\nVerify the file exists, evidence states remain honest, and the declared deterministic validator passes.",
            "## 중단·질문 조건\n\nStop when authority, owner, actual-use evidence, or a load-bearing decision is missing; ask only for closing evidence.",
        ]
        if name == "00-ORCHESTRATOR.md":
            body[4] += "\n\nRoute table:\n" + "\n".join(f"- `{prompt}`" for prompt in PROMPTS[1:])
        (prompt_dir / name).write_text("\n\n".join(body) + "\n", encoding="utf-8")
    write_report(root)


def run_validator(root: Path, legacy: bool) -> subprocess.CompletedProcess[str]:
    command = ["python3", str(VALIDATOR)]
    if legacy:
        command.append("--legacy-modernization")
    command.append(str(root))
    return subprocess.run(command, text=True, capture_output=True, check=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    failures: list[str] = []
    results: list[str] = []
    executed: list[str] = []
    successes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="plugify-svcplan-c02-") as temporary:
        base = Path(temporary)

        def execute(name: str, function) -> None:
            executed.append(name)
            try:
                function()
                successes.append(name)
                results.append(f"PASS {name}")
            except Exception as error:
                failures.append(f"{name}: {error}")
                results.append(f"FAIL {name}: {error}")

        legacy = base / "valid-legacy"
        make_package(legacy, legacy=True)

        def explicit_legacy_request_contract() -> None:
            require(REQUEST.is_file(), f"request fixture missing: {REQUEST}")
            request = REQUEST.read_text(encoding="utf-8")
            skill = SKILL.read_text(encoding="utf-8")
            system = SYSTEM.read_text(encoding="utf-8")
            for signal in [
                "기존 내부 업무 서비스를 현대화",
                "project context package",
                "역할 prompt",
                "실제 디렉터리 구조",
            ]:
                require(signal in request, f"request fixture lost signal: {signal}")
            require(
                "기존 서비스/ERP/내부 포털/데이터의 현대화·AX 전환이면 켠다"
                in skill,
                "explicit legacy-modernization activation contract missing",
            )
            require(
                skill.index("### P0b — 지속 문맥 골격과 legacy discovery gate")
                < skill.index("### P8 — 지속형 프로젝트 문맥 패키지"),
                "legacy discovery gate no longer precedes package construction",
            )
            observation = next(
                (
                    line
                    for line in system.splitlines()
                    if line.startswith("- service-planning persistent-context/legacy-modernization")
                ),
                "",
            )
            require("2026-08-26 출하" in observation, "post-release observation is not declared")
            require(
                "아침지기 AX package는 출하 전 forward test" in observation
                and "대신하지 않음" in observation,
                "forward test is being substituted for first post-release observation",
            )

        execute("explicit_legacy_request_contract", explicit_legacy_request_contract)

        execute(
            "valid_legacy_package",
            lambda: require(run_validator(legacy, True).returncode == 0, "valid legacy rejected"),
        )

        def missing_prompt() -> None:
            target = base / "missing-prompt"
            shutil.copytree(legacy, target)
            (target / "prompts/70-SECURITY-AI-REVIEWER.md").unlink()
            result = run_validator(target, True)
            require(result.returncode == 1 and "prompt set differs" in result.stdout, result.stdout)

        execute("missing_prompt_rejected", missing_prompt)

        def missing_heading() -> None:
            target = base / "missing-heading"
            shutil.copytree(legacy, target)
            path = target / "prompts/40-DATA-ARCHITECT.md"
            path.write_text(path.read_text(encoding="utf-8").replace("## 완료 검증", "## 검증 누락"), encoding="utf-8")
            write_report(target)
            result = run_validator(target, True)
            require(result.returncode == 1 and "heading count differs" in result.stdout, result.stdout)

        execute("missing_prompt_heading_rejected", missing_heading)

        def fenced_heading() -> None:
            target = base / "fenced-heading"
            shutil.copytree(legacy, target)
            path = target / "prompts/30-WORKFLOW-MODELER.md"
            hidden = "\n\n".join(
                f"{heading}\n\nTASK TARGETS OUTPUT EVIDENCE APPROVALS with enough filler for a fake section."
                for heading in HEADINGS
            )
            path.write_text(f"# disguised\n\n```markdown\n{hidden}\n```\n", encoding="utf-8")
            write_report(target)
            result = run_validator(target, True)
            require(result.returncode == 1 and "heading count differs" in result.stdout, result.stdout)

        execute("fenced_heading_rejected", fenced_heading)

        def route_gap() -> None:
            target = base / "route-gap"
            shutil.copytree(legacy, target)
            path = target / "prompts/00-ORCHESTRATOR.md"
            path.write_text(path.read_text(encoding="utf-8").replace("60-MIGRATION-PLANNER.md", "migration-role"), encoding="utf-8")
            write_report(target)
            result = run_validator(target, True)
            require(result.returncode == 1 and "orchestrator route missing" in result.stdout, result.stdout)

        execute("orchestrator_route_gap_rejected", route_gap)

        def commented_route() -> None:
            target = base / "commented-route"
            shutil.copytree(legacy, target)
            path = target / "prompts/00-ORCHESTRATOR.md"
            text = path.read_text(encoding="utf-8")
            for index, prompt in enumerate(PROMPTS[1:], start=1):
                text = text.replace(prompt, f"role-{index}")
            text += "\n<!-- " + " ".join(PROMPTS[1:]) + " -->\n"
            path.write_text(text, encoding="utf-8")
            write_report(target)
            result = run_validator(target, True)
            require(result.returncode == 1 and "orchestrator route missing" in result.stdout, result.stdout)

        execute("commented_route_rejected", commented_route)

        def stale_tree() -> None:
            target = base / "stale-tree"
            shutil.copytree(legacy, target)
            (target / "UNREPORTED.md").write_text("# unreported\n", encoding="utf-8")
            result = run_validator(target, True)
            require(result.returncode == 1 and "tree differs" in result.stdout, result.stdout)

        execute("stale_actual_tree_rejected", stale_tree)

        def fenced_tree() -> None:
            target = base / "fenced-tree"
            shutil.copytree(legacy, target)
            write_report(target)
            report = target / "DELIVERY-REPORT.md"
            tree = render_tree(target)
            visible = f"## 실제 디렉터리 구조\n\n```text\n{tree}\n```"
            text = report.read_text(encoding="utf-8")
            require(visible in text, "fixture visible tree block missing")
            text = text.replace(
                visible,
                "## 실제 디렉터리 구조\n\n가시적인 실제 tree가 없습니다.",
                1,
            )
            text += f"\n\n~~~markdown\n## 실제 디렉터리 구조\n\n```text\n{tree}\n```\n~~~\n"
            report.write_text(text, encoding="utf-8")
            result = run_validator(target, True)
            require(
                result.returncode == 1
                and "actual-tree text block missing" in result.stdout,
                result.stdout,
            )

        execute("fenced_tree_rejected", fenced_tree)

        def hidden_report(target: Path, opening: str, prelude: str, closing: str) -> None:
            shutil.copytree(legacy, target)
            write_report(target)
            report = target / "DELIVERY-REPORT.md"
            body = report.read_text(encoding="utf-8")
            report.write_text(
                f"{opening}\n{prelude}\n{body}\n{closing}\n",
                encoding="utf-8",
            )

        def long_fence() -> None:
            target = base / "long-fence"
            hidden_report(target, "````markdown", "```", "````")
            result = run_validator(target, True)
            require(
                result.returncode == 1
                and "heading count differs" in result.stdout
                and "actual-tree text block missing" in result.stdout,
                result.stdout,
            )

        execute("long_fence_rejected", long_fence)

        def trailing_text_fence() -> None:
            target = base / "trailing-text-fence"
            hidden_report(target, "````markdown", "````not-a-close", "````")
            result = run_validator(target, True)
            require(
                result.returncode == 1
                and "heading count differs" in result.stdout
                and "actual-tree text block missing" in result.stdout,
                result.stdout,
            )

        execute("trailing_text_fence_rejected", trailing_text_fence)

        def raw_html_structure() -> None:
            target = base / "raw-html-structure"
            shutil.copytree(legacy, target)
            write_report(target)
            report = target / "DELIVERY-REPORT.md"
            body = report.read_text(encoding="utf-8")
            report.write_text(f"<div>\n{body}\n</div>\n", encoding="utf-8")
            result = run_validator(target, True)
            require(
                result.returncode == 1
                and "raw HTML block is not allowed" in result.stdout,
                result.stdout,
            )

        execute("raw_html_structure_rejected", raw_html_structure)

        def processing_instruction_structure() -> None:
            target = base / "processing-instruction-structure"
            shutil.copytree(legacy, target)
            write_report(target)
            report = target / "DELIVERY-REPORT.md"
            body = report.read_text(encoding="utf-8")
            report.write_text(f"<?hidden\n{body}\n?>\n", encoding="utf-8")
            result = run_validator(target, True)
            require(
                result.returncode == 1
                and "raw HTML block is not allowed" in result.stdout,
                result.stdout,
            )

        execute(
            "processing_instruction_structure_rejected",
            processing_instruction_structure,
        )

        def flattened_tree() -> None:
            target = base / "flattened-tree"
            shutil.copytree(legacy, target)
            files = sorted(
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.is_file()
            )
            lines = [f"{target.name}/"]
            for index, relative in enumerate(files):
                connector = "└── " if index == len(files) - 1 else "├── "
                lines.append(f"{connector}{relative}")
            write_report(target, "\n".join(lines))
            result = run_validator(target, True)
            require(result.returncode == 1 and "invalid actual-tree path segment" in result.stdout, result.stdout)

        execute("flattened_tree_rejected", flattened_tree)

        def discovery_gap() -> None:
            target = base / "discovery-gap"
            shutil.copytree(legacy, target)
            (target / "PROCESS-CATALOG.md").unlink()
            write_report(target)
            result = run_validator(target, False)
            require(result.returncode == 1 and "required file missing" in result.stdout, result.stdout)

        execute("legacy_discovery_gap_rejected", discovery_gap)

        def conflicting_profile() -> None:
            target = base / "conflicting-profile"
            make_package(target, legacy=False)
            report = target / "DELIVERY-REPORT.md"
            text = report.read_text(encoding="utf-8").replace(
                "> profile: persistent-context",
                "> profile: persistent-context\n> profile: legacy-modernization",
                1,
            )
            report.write_text(text, encoding="utf-8")
            result = run_validator(target, False)
            require(
                result.returncode == 1
                and "profile declaration count differs" in result.stdout
                and "PROCESS-CATALOG.md" in result.stdout,
                result.stdout,
            )

        execute("conflicting_profile_rejected", conflicting_profile)

        def invalid_profile() -> None:
            target = base / "invalid-profile"
            make_package(target, legacy=False)
            report = target / "DELIVERY-REPORT.md"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    "> profile: persistent-context",
                    "> profile: standard",
                    1,
                ),
                encoding="utf-8",
            )
            result = run_validator(target, False)
            require(
                result.returncode == 1
                and "profile declaration missing or invalid" in result.stdout,
                result.stdout,
            )

        execute("invalid_profile_rejected", invalid_profile)

        def valid_nonlegacy() -> None:
            target = base / "valid-nonlegacy"
            make_package(target, legacy=False)
            require(run_validator(target, False).returncode == 0, "valid nonlegacy rejected")

        execute("valid_nonlegacy_package", valid_nonlegacy)

        def shipped_assets() -> None:
            for path in [VALIDATOR, REFERENCE, REPORT_ASSET, SKILL, BUILDER]:
                require(path.is_file() and path.stat().st_size > 0, f"missing {path}")
            reference = REFERENCE.read_text(encoding="utf-8")
            skill = SKILL.read_text(encoding="utf-8")
            asset = REPORT_ASSET.read_text(encoding="utf-8")
            for name in PROMPTS:
                require(name in reference, f"reference missing {name}")
            for heading in HEADINGS:
                require(heading in reference, f"reference missing {heading}")
            require("### P8 — 지속형 프로젝트 문맥 패키지" in skill, "SKILL P8 missing")
            require("## 실제 디렉터리 구조" in asset, "report asset tree section missing")

        execute("shipped_contract_assets", shipped_assets)

    if executed != TESTS:
        failure = f"test manifest mismatch: expected={TESTS}, executed={executed}"
        failures.append(failure)
        results.append(f"FAIL test_manifest_exact: {failure}")
    print(f"tests={len(TESTS)} passed={len(successes)} failed={len(failures)}")
    for result in results:
        print(result)
    for failure in failures:
        print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
