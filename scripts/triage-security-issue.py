from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.security_automation import classify_security_issue, load_issue_event


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a security issue for squad triage automation.')
    parser.add_argument('--event', required=True, help='Path to the GitHub issue event payload')
    parser.add_argument('--repo-root', default='.', help='Repository root used for manifest inspection')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    issue = load_issue_event(args.event)
    result = classify_security_issue(issue, args.repo_root)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_dict(), indent=2), encoding='utf-8')
    print(f'Wrote security triage result to {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
