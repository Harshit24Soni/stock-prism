import os
import unittest
import logging
from unittest.mock import patch
from StockPrism.utils.logger import get_logger


class TestLogger(unittest.TestCase):
    def test_get_logger_instance(self):
        logger = get_logger("test_module")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_module")

    def test_logger_fallback_on_os_error(self):
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Read-only filesystem")):
            # Should not raise exception
            fallback_logger = get_logger("fallback_module")
            self.assertIsInstance(fallback_logger, logging.Logger)


if __name__ == "__main__":
    unittest.main()

