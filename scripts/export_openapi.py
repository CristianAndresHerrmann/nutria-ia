"""Exporta el contrato vigente para versionarlo en los repos que lo consumen."""

import argparse
import json
from pathlib import Path

from app.main import app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outputs", nargs="+", type=Path, help="Archivos JSON de destino")
    args = parser.parse_args()
    content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    for output in args.outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"Contrato exportado: {output}")


if __name__ == "__main__":
    main()
