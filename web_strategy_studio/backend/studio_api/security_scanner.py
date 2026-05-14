"""AST-based security checks for user strategy source (MVP).

.. warning::
    **This scanner is a "friendly lint" tool, NOT a security sandbox.**

    The AST denylist approach cannot prevent a determined attacker from
    executing arbitrary code.  Known bypasses include::

        # String-concatenated names evade name-based checks
        getattr(__builtins__, "ev"+"al")("__import__('os').system('rm -rf /')")

        # Object subclass traversal finds Popen
        object.__subclasses__()[...]  # search for subprocess.Popen

        # Split-string imports
        __import__('o'+'s')

    For real sandboxing use system-level isolation: run each backtest in a
    dedicated Docker container with ``--network none --read-only
    --pids-limit=64 --memory=2g --cpus=1 --security-opt seccomp=...`` and a
    non-root user.  The AST checks here catch *accidental* use of restricted
    modules by well-meaning users and provide clear error messages, nothing more.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class SecurityNote:
    code: str
    line: int
    col: int
    message: str


# Imports not allowed in user strategies (extend as needed)
BANNED_MODULES = frozenset(
    {
        "subprocess",
        "multiprocessing",
        "socket",
        "ctypes",
        "ssl",
        "http",
        "urllib",
        "urllib2",
        "ftplib",
        "smtplib",
        "telnetlib",
        "pickle",
        "shelve",
        "marshal",
        "os",
        "sys",
        "shutil",
        "pty",
        "resource",
        "importlib",
        "code",
        "commands",
        "builtins",
    }
)

ALLOWED_TOP_LEVEL = frozenset(
    {
        "eqlib",
        "math",
        "random",
        "datetime",
        "decimal",
        "typing",
        "collections",
        "itertools",
        "functools",
        "re",
        "json",
        "copy",
        "abc",
        "enum",
        "pathlib",
        "pandas",
        "numpy",
        "pd",
        "np",
    }
)


class SecurityScanner:
    def scan(self, source: str) -> list[SecurityNote]:
        notes: list[SecurityNote] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return notes  # syntax handled elsewhere

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in BANNED_MODULES:
                        notes.append(
                            SecurityNote(
                                code="EQ-BANNED-IMPORT",
                                line=node.lineno or 1,
                                col=node.col_offset or 0,
                                message=f"Import '{root}' is not allowed in user strategies",
                            )
                        )
                    elif root not in ALLOWED_TOP_LEVEL and root != "":
                        notes.append(
                            SecurityNote(
                                code="EQ-IMPORT-WARN",
                                line=node.lineno or 1,
                                col=node.col_offset or 0,
                                message=f"Import '{root}' may be restricted; prefer eqlib / numpy / pandas",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in BANNED_MODULES:
                        notes.append(
                            SecurityNote(
                                code="EQ-BANNED-IMPORT",
                                line=node.lineno or 1,
                                col=node.col_offset or 0,
                                message=f"Import from '{root}' is not allowed in user strategies",
                            )
                        )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "__import__"):
                    notes.append(
                        SecurityNote(
                            code="EQ-BANNED-CALL",
                            line=node.lineno or 1,
                            col=node.col_offset or 0,
                            message=f"Call to '{node.func.id}' is not allowed",
                        )
                    )
        return notes


def require_initialize_function(source: str) -> list[SecurityNote]:
    notes: list[SecurityNote] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return notes
    found = any(
        isinstance(n, ast.FunctionDef) and n.name == "initialize"
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    if not found:
        notes.append(
            SecurityNote(
                code="EQ-MISSING-INIT",
                line=1,
                col=0,
                message="Strategy must define def initialize(context)",
            )
        )
    return notes
