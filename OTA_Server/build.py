#==============================================================================
# File: build.py
#
# Description:
#     Build QuecPython OTA application files.
#
#     Build process:
#
#         1. Read project.json.
#         2. Optionally increment application version.
#         3. Recursively process all files in src/.
#         4. Compile every .py file to .mpy using mpy-cross.
#         5. Copy all other files without modification.
#         6. Preserve the directory structure from src/.
#         7. Calculate SHA-256 for every generated OTA file.
#         8. Generate manifest.json.
#         9. Replace files/ only after the build has completed successfully.
#
# Usage:
#
#     python build.py
#
#         Build without changing the version.
#
#     python build.py --patch
#
#         Increment patch version and build.
#
#     python build.py --minor
#
#         Increment minor version and reset patch to 0.
#
#     python build.py --major
#
#         Increment major version and reset minor and patch to 0.
#
#==============================================================================

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------

BASE_DIRECTORY = Path(__file__).resolve().parent

PROJECT_FILE = BASE_DIRECTORY / "project.json"
MANIFEST_FILE = BASE_DIRECTORY / "manifest.json"

SOURCE_DIRECTORY = BASE_DIRECTORY / "src"
FILES_DIRECTORY = BASE_DIRECTORY / "files"

MPY_CROSS = BASE_DIRECTORY / "tools" / "mpy-cross-amd64.exe"


# ------------------------------------------------------------------------------
# Project
# ------------------------------------------------------------------------------

def load_project():
    with PROJECT_FILE.open("r", encoding="utf-8") as file:
        project = json.load(file)

    validate_project(project)

    return project


def validate_project(project):
    if not isinstance(project, dict):
        raise ValueError("project.json must contain a JSON object.")

    required_fields = [
        "project",
        "version",
        "description"
    ]

    for field in required_fields:
        if field not in project:
            raise ValueError(
                "Missing field in project.json: {}".format(field)
            )

    if not isinstance(project["version"], dict):
        raise ValueError("The 'version' field must be an object.")

    required_version_fields = [
        "major",
        "minor",
        "patch"
    ]

    for field in required_version_fields:
        if field not in project["version"]:
            raise ValueError(
                "Missing version field: {}".format(field)
            )

        # bool is a subclass of int in Python, therefore use type() here.
        if type(project["version"][field]) is not int:
            raise ValueError(
                "Version field '{}' must be an integer.".format(field)
            )

        if project["version"][field] < 0:
            raise ValueError(
                "Version field '{}' cannot be negative.".format(field)
            )

def update_version(project):
    version = project["version"]

    flags = [
        flag
        for flag in ("--patch", "--minor", "--major")
        if flag in sys.argv[1:]
    ]

    if len(flags) > 1:
        raise ValueError(
            "Use only one version flag: --patch, --minor or --major."
        )

    if not flags:
        return

    flag = flags[0]

    if flag == "--patch":
        version["patch"] += 1

    elif flag == "--minor":
        version["minor"] += 1
        version["patch"] = 0

    elif flag == "--major":
        version["major"] += 1
        version["minor"] = 0
        version["patch"] = 0


def version_string(project):
    version = project["version"]

    return "{}.{}.{}".format(
        version["major"],
        version["minor"],
        version["patch"]
    )


# ------------------------------------------------------------------------------
# Hash
# ------------------------------------------------------------------------------

def calculate_sha256(filename):
    sha = hashlib.sha256()

    with filename.open("rb") as file:
        while True:
            data = file.read(4096)

            if not data:
                break

            sha.update(data)

    return sha.hexdigest()


# ------------------------------------------------------------------------------
# Environment
# ------------------------------------------------------------------------------

def validate_environment():
    if not SOURCE_DIRECTORY.is_dir():
        raise FileNotFoundError(
            "Source directory not found: {}".format(
                SOURCE_DIRECTORY
            )
        )

    if not MPY_CROSS.is_file():
        raise FileNotFoundError(
            "mpy-cross executable not found: {}".format(
                MPY_CROSS
            )
        )


# ------------------------------------------------------------------------------
# Compilation
# ------------------------------------------------------------------------------

def compile_python(source_file, output_file):
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    command = [
        str(MPY_CROSS),
        "-mno-unicode",
        str(source_file),
        "-o",
        str(output_file)
    ]

    result = subprocess.run(
        command,
        cwd=str(BASE_DIRECTORY)
    )

    if result.returncode != 0:
        raise RuntimeError(
            "mpy-cross failed for: {}".format(source_file)
        )


# ------------------------------------------------------------------------------
# Build files
# ------------------------------------------------------------------------------

def build_files(temp_directory):
    file_count = 0
    output_paths = set()

    for source_file in sorted(SOURCE_DIRECTORY.rglob("*")):
        if not source_file.is_file():
            continue

        relative_path = source_file.relative_to(SOURCE_DIRECTORY)

        if source_file.suffix.lower() == ".py":
            output_relative_path = relative_path.with_suffix(".mpy")
            output_file = temp_directory / output_relative_path

            print(
                "  PY -> MPY:",
                relative_path,
                "->",
                output_relative_path
            )

            compile_python(source_file, output_file)

        else:
            output_relative_path = relative_path
            output_file = temp_directory / output_relative_path

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            print("  COPY    :", relative_path)

            shutil.copy2(source_file, output_file)

        # Prevent ambiguous source layouts such as:
        # src/app.py + src/app.mpy -> both produce files/app.mpy.
        if output_relative_path in output_paths:
            raise RuntimeError(
                "Output file collision: {}".format(
                    output_relative_path
                )
            )

        output_paths.add(output_relative_path)
        file_count += 1

    if file_count == 0:
        raise RuntimeError("The 'src' directory is empty.")

    return file_count


# ------------------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------------------

def build_manifest(project, directory):
    now = datetime.now()

    manifest = {
        "project": project["project"],
        "version": version_string(project),
        "description": project["description"],
        "build": {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S")
        },
        "files": []
    }

    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(directory)
        relative_name = relative_path.as_posix()

        manifest["files"].append({
            "name": relative_name,
            "path": "/files/" + relative_name,
            "size": file_path.stat().st_size,
            "sha256": calculate_sha256(file_path)
        })

    if not manifest["files"]:
        raise RuntimeError("The build contains no OTA files.")

    return manifest


# ------------------------------------------------------------------------------
# Transaction
# ------------------------------------------------------------------------------

def prepare_json_file(path, data):
    temporary_file = path.with_name(
        path.name + ".tmp"
    )

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)
        file.write("\n")

    return temporary_file


def remove_path(path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def restore_backup(backup, target):
    if target.exists():
        remove_path(target)

    if backup.exists():
        backup.rename(target)


def install_build(
    temp_directory,
    temporary_project,
    temporary_manifest
):
    files_backup = FILES_DIRECTORY.with_name(
        FILES_DIRECTORY.name + ".old"
    )

    project_backup = PROJECT_FILE.with_name(
        PROJECT_FILE.name + ".old"
    )

    manifest_backup = MANIFEST_FILE.with_name(
        MANIFEST_FILE.name + ".old"
    )

    backups = [
        (FILES_DIRECTORY, files_backup),
        (PROJECT_FILE, project_backup),
        (MANIFEST_FILE, manifest_backup)
    ]

    # A leftover .old means a previous transaction may not have completed.
    # Do not silently delete it because it may contain the last known-good build.
    for _, backup in backups:
        if backup.exists():
            raise RuntimeError(
                "Backup file/directory already exists: {}".format(backup)
            )

    try:
        # Move current state out of the way.
        for target, backup in backups:
            if target.exists():
                target.rename(backup)

        # Install the new files and metadata.
        temp_directory.rename(FILES_DIRECTORY)
        temporary_project.rename(PROJECT_FILE)
        temporary_manifest.rename(MANIFEST_FILE)

    except Exception as error:
        rollback_errors = []

        # Remove whatever part of the new state was installed.
        for target, _ in backups:
            try:
                if target.exists():
                    remove_path(target)
            except Exception as rollback_error:
                rollback_errors.append(
                    "remove {}: {}".format(target, rollback_error)
                )

        # Restore the previous state.
        for target, backup in backups:
            try:
                restore_backup(backup, target)
            except Exception as rollback_error:
                rollback_errors.append(
                    "restore {}: {}".format(target, rollback_error)
                )

        message = "Build installation failed: {}".format(error)

        if rollback_errors:
            message += (
                "\nRollback also failed:\n  - "
                + "\n  - ".join(rollback_errors)
            )

        raise RuntimeError(message) from error

    # The new state is complete. Old state is no longer needed.
    cleanup_errors = []

    for _, backup in backups:
        try:
            if backup.exists():
                remove_path(backup)
        except Exception as error:
            cleanup_errors.append(
                "Could not remove backup {}: {}".format(
                    backup,
                    error
                )
            )

    for message in cleanup_errors:
        print("WARNING:", message)


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    print()
    print("========================================")
    print("QuecPython OTA Build")
    print("========================================")
    print()

    validate_environment()

    project = load_project()
    update_version(project)

    print("Version :", version_string(project))
    print("Source  :", SOURCE_DIRECTORY)
    print("Output  :", FILES_DIRECTORY)
    print("Compiler:", MPY_CROSS)
    print()

    with tempfile.TemporaryDirectory(
        prefix=".ota_build_",
        dir=str(BASE_DIRECTORY)
    ) as temporary_directory:

        temporary_directory = Path(temporary_directory)

        print("Building files...")
        print()

        file_count = build_files(temporary_directory)

        print()
        print("Generating manifest...")
        print()

        manifest = build_manifest(
            project,
            temporary_directory
        )

        # Prepare both JSON files before touching the live files/ directory.
        temporary_project = prepare_json_file(
            PROJECT_FILE,
            project
        )

        temporary_manifest = prepare_json_file(
            MANIFEST_FILE,
            manifest
        )

        print()
        print("Installing {} files...".format(file_count))
        print()

        install_build(
            temporary_directory,
            temporary_project,
            temporary_manifest
        )

    print()
    print("Build successful.")
    print("Version :", version_string(project))
    print("Files   :", file_count)
    print()


# ------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print()
        print("BUILD FAILED:")
        print(error)
        sys.exit(1)
