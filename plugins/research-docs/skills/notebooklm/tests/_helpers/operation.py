"""Client-shaped operation context for tests of application result projection.

Runtime admission, deadlines, and lifecycle are exercised with real clients in
operation-scope tests; these doubles keep renderer/service tests independent of I/O.
"""

from contextlib import nullcontext
from types import SimpleNamespace

from notebooklm.options import UseDefault


class ClientStub(SimpleNamespace):
    def operation(self, timeout: float | None | UseDefault = None) -> nullcontext[None]:
        return nullcontext()
