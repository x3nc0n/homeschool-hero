from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.security_automation import apply_patch_plan, build_patch_plan, load_issue_event, parse_security_issue


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply a guarded dependency auto-patch for a security issue.')
    parser.add_argument('--event', required=True, help='Path to the GitHub issue event payload')
    parser.add_argument('--repo-root', default='.', help='Repository root used for manifest updates')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    issue_payload = load_issue_event(args.event)
    issue = parse_security_issue(issue_payload)
    plan = build_patch_plan(issue, args.repo_root)
    if not plan:
        raise SystemExit('Issue is not eligible for automated dependency patching.')

    changed_files = apply_patch_plan(plan, args.repo_root)
    payload = {
        'issue': issue,
        'patch_plan': plan.to_dict(),
        'changed_files': changed_files,
        'noop': not changed_files,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f'Applied auto-patch plan and wrote metadata to {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
