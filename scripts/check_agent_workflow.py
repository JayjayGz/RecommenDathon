"""Read-only structural checks for development agent files and lesson memory."""

import argparse
import copy
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    "data", "screening", "risk", "portfolio", "backtest", "evidence",
    "explanation", "compliance", "infrastructure",
}
FIELDS = {
    "id", "roles", "trigger", "boundary", "defect", "cause", "evidence",
    "prevention", "regression", "status", "verification",
}


def validate_memory(memory):
    errors = []
    if not isinstance(memory, dict) or memory.get("schema_version") != 1:
        return ["memory must be an object with schema_version 1"]
    lessons = memory.get("lessons")
    if not isinstance(lessons, list):
        return ["lessons must be a list"]
    seen = set()
    for index, lesson in enumerate(lessons):
        label = f"lesson[{index}]"
        if not isinstance(lesson, dict):
            errors.append(f"{label}: expected object")
            continue
        missing = FIELDS - lesson.keys()
        if missing:
            errors.append(f"{label}: missing {', '.join(sorted(missing))}")
        lesson_id = lesson.get("id")
        if not isinstance(lesson_id, str) or not re.fullmatch(r"L-\d{3,}", lesson_id):
            errors.append(f"{label}: invalid ID")
        elif lesson_id in seen:
            errors.append(f"{label}: duplicate ID {lesson_id}")
        else:
            seen.add(lesson_id)
        roles = lesson.get("roles")
        if (not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) or role not in ROLES | {"all"}
                       for role in roles)):
            errors.append(f"{label}: invalid roles")
        for field in ("trigger", "boundary", "defect", "cause", "prevention", "regression"):
            value = lesson.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: {field} must be nonempty text")
        evidence = lesson.get("evidence")
        if (not isinstance(evidence, list) or not evidence
                or any(not isinstance(item, str) or not item.strip() for item in evidence)):
            errors.append(f"{label}: evidence must contain nonempty references")
        status = lesson.get("status")
        if status not in ("documented", "verified", "superseded"):
            errors.append(f"{label}: invalid status")
        verification = lesson.get("verification")
        if not isinstance(verification, list):
            errors.append(f"{label}: verification must be a list")
        else:
            if status == "verified" and not verification:
                errors.append(f"{label}: verified status requires recorded checks")
            for check in verification:
                if not isinstance(check, dict) or any(
                    not isinstance(check.get(key), str) or not check[key].strip()
                    for key in ("command", "result", "scope")
                ):
                    errors.append(f"{label}: invalid verification entry")
    return errors


def check_files(root):
    errors = []
    router = (root / "AGENTS.md").read_text(encoding="utf-8")
    expected = {f"agents/{role}-agent.md" for role in ROLES}
    referenced = set(re.findall(r"agents/[a-z]+-agent\.md", router))
    if referenced != expected:
        errors.append("router specialist paths do not match the expected roles")
    actual = {path.relative_to(root).as_posix() for path in (root / "agents").rglob("*.md")}
    if actual != expected:
        errors.append("agent files must use the nine flat <role>-agent.md filenames")
    for relative in sorted(expected):
        path = root / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for required in ("## Selection and boundaries", "## Learning and replay",
                         "memory/lessons.json", "docs/agent-correction-protocol.md"):
            if required not in text:
                errors.append(f"{relative}: missing {required}")
    protocol = root / "docs/agent-correction-protocol.md"
    if not protocol.is_file() or not protocol.read_text(encoding="utf-8").strip():
        errors.append("missing or empty correction protocol")
    memory = json.loads((root / "memory/lessons.json").read_text(encoding="utf-8"))
    errors.extend(validate_memory(memory))
    return errors, memory


class MemoryChecks(unittest.TestCase):
    def setUp(self):
        self.lesson = dict.fromkeys(FIELDS, "specific example")
        self.lesson.update(id="L-001", roles=["data"], evidence=["fixture observation"],
                           status="documented", verification=[])

    def errors(self, lessons=None):
        return validate_memory({"schema_version": 1, "lessons":
                                lessons if lessons is not None else [self.lesson]})

    def test_valid_documented_control(self):
        self.assertEqual(self.errors(), [])

    def test_duplicate_id(self):
        self.assertTrue(self.errors([self.lesson, copy.deepcopy(self.lesson)]))

    def test_unknown_role(self):
        self.lesson["roles"] = ["invented"]
        self.assertTrue(self.errors())

    def test_unnamed_defect(self):
        self.lesson["defect"] = " "
        self.assertTrue(self.errors())

    def test_verified_without_checks(self):
        self.lesson["status"] = "verified"
        self.assertTrue(self.errors())

    def test_verified_with_scoped_check_control(self):
        self.lesson.update(status="verified", verification=[{
            "command": "fixture check", "result": "passed", "scope": "structure only"}])
        self.assertEqual(self.errors(), [])

    def test_missing_evidence(self):
        self.lesson["evidence"] = []
        self.assertTrue(self.errors())

    def test_bad_top_level(self):
        self.assertTrue(validate_memory([]))
        self.assertTrue(validate_memory({"schema_version": 1, "lessons": "invalid"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--lessons-for", choices=sorted(ROLES))
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(MemoryChecks))
        return 0 if result.wasSuccessful() else 1
    try:
        errors, memory = check_files(ROOT)
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if args.lessons_for:
        lessons = [lesson for lesson in memory["lessons"]
                   if lesson["status"] != "superseded"
                   and ({"all", args.lessons_for} & set(lesson["roles"]))]
        print(json.dumps(lessons, indent=2, ensure_ascii=False))
    else:
        print(f"PASS: {len(ROLES)} agent files; {len(memory['lessons'])} lesson records. "
              "Structure only; no behavioral or runtime enforcement claim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
