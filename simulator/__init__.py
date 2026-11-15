"""CruxTrap attacker simulator and RL experiments (Phase 5)."""
# The exact solver does thousands of small (~330x330) linear solves. Multi-threaded
# OpenBLAS makes each one ~100x slower on Windows (thread start-up dominates), so pin
# BLAS to one thread; experiments parallelise across processes instead.
# Env vars cover a numpy that is not imported yet; threadpoolctl covers one that is.
# (threadpoolctl only sees libraries already loaded, hence importing numpy first.)
import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as _np  # noqa: E402,F401  (load BLAS so the limit below applies to it)

try:
    from threadpoolctl import threadpool_limits

    threadpool_limits(limits=1, user_api="blas")
except ImportError:  # pragma: no cover
    pass
