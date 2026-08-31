#!/usr/bin/env python3
"""Plant retired contracts and prove the public-docs ratchet sees them."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "sdk_contract_gate.py"
SPEC = importlib.util.spec_from_file_location("sdk_contract_gate", SCRIPT)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


class SdkContractGateTest(unittest.TestCase):
    def test_clean_one_sdk_document_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sdk").mkdir()
            (root / "sdk" / "run.mdx").write_text(
                "const run = await nika.run(file)\nawait run.done\n",
                encoding="utf-8",
            )
            self.assertEqual([], GATE.findings(root))

    def test_retired_contract_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sdk").mkdir()
            (root / "sdk" / "legacy.mdx").write_text(
                "import { LocalNika } from '@supernovae-st/nika-client/local'\n",
                encoding="utf-8",
            )
            failures = GATE.findings(root)
            self.assertTrue(any("split local class" in item for item in failures))
            self.assertTrue(any("split local import" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
