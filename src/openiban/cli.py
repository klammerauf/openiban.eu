"""Local maintainer CLI; no unauthenticated HTTP write endpoints."""

import argparse
import json
import os
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from openiban.bundesbank import SOURCE_URL
from openiban.directories import SOURCES
from openiban.directory_download import download_directory
from openiban.directory_storage import (
    activate_directory,
    list_directory_versions,
    stage_directory,
)
from openiban.storage import activate, build_engine, initialize, list_versions, stage_file


def main() -> None:
    parser = argparse.ArgumentParser(prog="openiban")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Initiales Datenbankschema anlegen")
    importer = commands.add_parser("import-bundesbank", help="Öffentliche TXT prüfen und vormerken")
    importer.add_argument("file", type=Path)
    importer.add_argument("--valid-from", type=date.fromisoformat, required=True)
    importer.add_argument("--valid-until", type=date.fromisoformat, required=True)
    importer.add_argument("--source-url", default=SOURCE_URL)
    downloader = commands.add_parser(
        "fetch-directory", help="Offizielles Verzeichnis herunterladen"
    )
    downloader.add_argument("country", choices=sorted(SOURCES))
    downloader.add_argument("file", type=Path)
    downloader.add_argument("--source-url")
    directory = commands.add_parser("import-directory", help="Verzeichnis prüfen und vormerken")
    directory.add_argument("country", choices=sorted(SOURCES))
    directory.add_argument("file", type=Path)
    directory.add_argument("--valid-from", type=date.fromisoformat, required=True)
    directory.add_argument("--valid-until", type=date.fromisoformat, required=True)
    directory.add_argument("--source-url", required=True)
    country_activate = commands.add_parser(
        "activate-directory", help="Geprüften Landesbestand aktivieren"
    )
    country_activate.add_argument("country", choices=sorted(SOURCES))
    country_activate.add_argument("version")
    country_activate.add_argument("--review-note", required=True)
    country_activate.add_argument("--allow-expired", action="store_true")
    directory_versions = commands.add_parser("directory-versions")
    directory_versions.add_argument("country", choices=sorted(SOURCES))
    activator = commands.add_parser(
        "activate", help="Geprüfte Version aktivieren oder zurücksetzen"
    )
    activator.add_argument("version")
    activator.add_argument("--allow-expired", action="store_true")
    commands.add_parser("versions", help="Datenversionen anzeigen")
    for name in ("auto-check", "auto-activate", "update-status"):
        command = commands.add_parser(name)
        command.add_argument(
            "--state-dir",
            type=Path,
            default=Path(os.environ.get("OPENIBAN_UPDATE_DIR", "/var/lib/openiban/updates")),
        )
        if name == "auto-check":
            command.add_argument("--activate-due", action="store_true")
    args = parser.parse_args()
    engine = build_engine()
    try:
        if args.command == "init-db":
            initialize(engine)
            output = {"status": "initialized"}
        elif args.command == "import-bundesbank":
            output = stage_file(
                engine, args.file, args.valid_from, args.valid_until, args.source_url
            )
        elif args.command == "fetch-directory":
            content, source_url = download_directory(args.country, args.source_url)
            with args.file.open("xb") as handle:
                handle.write(content)
            output = {"country": args.country, "file": str(args.file), "source_url": source_url}
        elif args.command == "import-directory":
            output = stage_directory(
                engine, args.country, args.file, args.valid_from, args.valid_until, args.source_url
            )
        elif args.command == "activate-directory":
            activate_directory(
                engine,
                args.country,
                args.version,
                review_note=args.review_note,
                allow_expired=args.allow_expired,
            )
            output = {"status": "active", "country": args.country, "version": args.version}
        elif args.command == "directory-versions":
            output = list_directory_versions(engine, args.country)
        elif args.command == "activate":
            activate(engine, args.version, allow_expired=args.allow_expired)
            output = {"status": "active", "version": args.version}
        elif args.command in {"auto-check", "auto-activate", "update-status"}:
            from openiban.updater import auto_activate, auto_check, update_status

            if args.command == "auto-check":
                output = auto_check(engine, args.state_dir)
                if args.activate_due:
                    output = auto_activate(engine, args.state_dir)
            elif args.command == "auto-activate":
                output = auto_activate(engine, args.state_dir)
            else:
                output = update_status(engine, args.state_dir)
        else:
            output = list_versions(engine)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Fehler: {exc}\n")
    except SQLAlchemyError:
        parser.exit(
            1, "Datenbankfehler. Verbindung prüfen und zuerst 'openiban init-db' ausführen.\n"
        )
    finally:
        engine.dispose()
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    if isinstance(output, dict) and output.get("warnings"):
        parser.exit(2, "Updater-Warnung: Details siehe JSON-Ausgabe.\n")


if __name__ == "__main__":
    main()
