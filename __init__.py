import hashlib
import importlib.util
import sys
from pathlib import Path


def _package():
    root = Path(__file__).resolve().parent
    if root.name == "dashboard":
        root = root.parent
    name = "_hermes_paseo_" + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / "paseo_executive" / "__init__.py",
                                                     submodule_search_locations=[str(root / "paseo_executive")])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return name


def register(ctx):
    from importlib import import_module
    import_module(_package() + ".tools").register(ctx)
