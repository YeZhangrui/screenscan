"""统一文件日志：无控制台的打包环境也能排查问题。"""
from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import data_dir


def setup_logging() -> Path:
    log_dir = data_dir() / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"
    handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)

    def excepthook(exc_type, exc, tb):
        root.error("未捕获异常:\n" + "".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = excepthook

    def thread_excepthook(args):
        name = args.thread.name if args.thread else "?"
        root.error(
            f"线程异常[{name}]:\n"
            + "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
            )
        )

    threading.excepthook = thread_excepthook
    return log_file
