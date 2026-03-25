"""Build Svelte frontend and copy into Python package for serving."""
import subprocess, shutil
from pathlib import Path

FRONTEND = Path("frontend")
STATIC = Path("src/wabbajack/web/static")


def build():
    print("Building Svelte frontend...")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)

    print(f"Copying build to {STATIC}...")
    if STATIC.exists():
        shutil.rmtree(STATIC)
    shutil.copytree(FRONTEND / "dist", STATIC)
    count = sum(1 for _ in STATIC.rglob('*') if _.is_file())
    print(f"Done. {count} files copied to {STATIC}")


if __name__ == "__main__":
    build()
