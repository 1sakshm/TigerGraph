"""Package the real HHGOA case outputs as a read-only GitHub Pages preview.

GitHub Pages cannot run the Python investigator. This builder deliberately
publishes only generated answers, traces, and the existing benchmark viewer.
"""

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def build(root: Path, output: Path) -> None:
    source = root / "cases"
    answers = sorted(source.glob("HHG-???.json"))
    expected = [f"HHG-{number:03d}" for number in range(1, 21)]
    if [path.stem for path in answers] != expected:
        raise ValueError("The Pages preview requires all 20 benchmark answers")

    output.mkdir(parents=True, exist_ok=True)
    static = output / "static"
    data = output / "data"
    traces = data / "investigations"
    static.mkdir(exist_ok=True)
    traces.mkdir(parents=True, exist_ok=True)

    page = (root / "frontend/benchmark.html").read_text(encoding="utf-8")
    page = page.replace('<html lang="en">', '<html lang="en" data-static-preview="true">')
    page = page.replace('href="/static/', 'href="./static/')
    page = page.replace('src="/static/', 'src="./static/')
    page = page.replace(
        '<a class="header-link" href="/">Live investigator</a>',
        '<a class="header-link" href="https://github.com/1sakshm/TigerGraph">Read-only preview · source</a>',
    )
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    for name in ("style.css", "benchmark.css", "benchmark.js"):
        shutil.copyfile(root / "frontend" / name, static / name)

    summaries = []
    for path in answers:
        answer = json.loads(path.read_text(encoding="utf-8"))
        case = answer["case"]
        summaries.append({
            "case_id": answer["case_id"], "verdict": case["verdict"],
            "pattern": case["pattern"], "fraud_probability": case["fraud_probability"],
            "status": case["status"], "written_to_graph": case["written_to_graph"],
            "initial_action": answer["next_best_actions"]["initial"][0]["action"],
            "final_action": answer["next_best_actions"]["final"][0]["action"],
        })
        shutil.copyfile(path, data / path.name)
        trace = source / "investigations" / path.name
        if not trace.is_file():
            raise ValueError(f"Missing investigation trace for {path.stem}")
        shutil.copyfile(trace, traces / path.name)
    (data / "index.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    build(ROOT, args.output)
    print(f"Built read-only benchmark preview at {args.output}")


if __name__ == "__main__":
    main()
