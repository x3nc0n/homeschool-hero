from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.security_issue_utils import deduplicate_findings, parse_trivy_reports


def main() -> int:
    parser = argparse.ArgumentParser(description='Parse Trivy JSON reports into normalized finding JSON.')
    parser.add_argument('--input', nargs='+', required=True, help='Trivy JSON file or directory paths')
    parser.add_argument('--ignorefile', help='Optional .trivyignore path for suppression detection')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    findings = deduplicate_findings(parse_trivy_reports(args.input, args.ignorefile))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(findings, indent=2), encoding='utf-8')
    print(f'Parsed {len(findings)} Trivy findings into {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
