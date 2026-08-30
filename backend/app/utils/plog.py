# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Project root the way config.py sees it: backend/
# (plog.py lives in backend/app/utils/ so resolve three levels up)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

_HANDLERS_READY = False


def pipeline_logger() -> logging.Logger:
    """Logger for the AI failure-analysis pipeline. Writes the stage markers
    (PAYMENT_CREATED, ANOMALY_CHECK_STARTED, GROQ_REQUEST_*, …) to stderr AND
    to backend/pipeline.log so failures are always obvious, independent of
    uvicorn's --log-level."""

    global _HANDLERS_READY

    logger = logging.getLogger("pulseops.pipeline")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not _HANDLERS_READY and not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        stream.setLevel(logging.INFO)
        logger.addHandler(stream)

        file = logging.FileHandler(BASE_DIR / "pipeline.log", encoding="utf-8")
        file.setFormatter(fmt)
        file.setLevel(logging.INFO)
        logger.addHandler(file)

        _HANDLERS_READY = True

    return logger


def plog(message: str, level: str = "info") -> None:
    log = pipeline_logger()
    getattr(log, level.lower(), log.info)(message)