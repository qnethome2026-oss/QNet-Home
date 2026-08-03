"""Minimal no-op numba stub for Windows-on-ARM (no numba/llvmlite win_arm64 wheels).
librosa imports numba at module scope; the JIT is a pure optimisation, so pass-through
decorators give correct (slower) results. Only the small helpers in librosa.filters /
librosa.util are affected -- not the hot path, which is torch/ONNX."""
import functools
__version__ = "0.0.0-qnet-stub"

def _passthrough_decorator(*dargs, **dkw):
    # supports @jit, @jit(...), @jit(nopython=True), @jit(signature)
    if len(dargs) == 1 and callable(dargs[0]) and not dkw:
        return dargs[0]
    def wrap(fn):
        return fn
    return wrap

jit = njit = generated_jit = _passthrough_decorator
vectorize = guvectorize = stencil = cfunc = _passthrough_decorator
prange = range

def set_num_threads(n): pass
def get_num_threads(): return 1
def objmode(*a, **k):
    import contextlib; return contextlib.nullcontext()

class _Types:
    def __getattr__(self, name):
        return None
types = _Types()

class TypingError(Exception): pass
class NumbaError(Exception): pass
class _Core:
    class errors:
        TypingError = TypingError
        NumbaError = NumbaError
        NumbaWarning = UserWarning
        NumbaDeprecationWarning = DeprecationWarning
core = _Core()
errors = _Core.errors
