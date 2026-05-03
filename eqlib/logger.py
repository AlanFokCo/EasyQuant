"""Logging facility (mirrors EasyQuant's log object)."""

import logging
import datetime

# Internal logger
_logger = logging.getLogger("eqlib")
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s",
                                        datefmt="%H:%M:%S"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)


class Logger:
    """User-facing logger (mirrors EasyQuant's log object)."""

    @staticmethod
    def info(msg, *args):
        _logger.info(msg, *args)

    @staticmethod
    def debug(msg, *args):
        _logger.debug(msg, *args)

    @staticmethod
    def warn(msg, *args):
        _logger.warning(msg, *args)

    @staticmethod
    def error(msg, *args):
        _logger.error(msg, *args)


log = Logger()
