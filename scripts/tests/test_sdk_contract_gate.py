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
    def check_document(self, text: str, relative: str = "sdk/run.mdx") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            file = root / relative
            file.parent.mkdir(parents=True)
            file.write_text(text, encoding="utf-8")
            return GATE.findings(root)

    def test_callout_requires_explicit_canonical_data(self) -> None:
        imported = 'import { SDK, LocalContract } from "/snippets/_sdk-contract.mdx"\n'
        self.assertEqual([], self.check_document(imported + '<LocalContract sdk={SDK} />'))
        for callout in ("SourceContract", "LocalContract", "RemoteContract"):
            with self.subTest(callout=callout):
                self.assertTrue(self.check_document(imported + f'<{callout} />'))
                self.assertTrue(self.check_document(f'<{callout} sdk={{SDK}} />'))
                self.assertTrue(self.check_document(imported + f'<{callout} sdk={{other}} />'))

    def test_a_different_import_is_not_the_canonical_sdk_data(self) -> None:
        self.assertTrue(self.check_document(
            'import { SDK } from "/different.mdx"\n<LocalContract sdk={SDK} />'
        ))

    def test_shared_components_cannot_rely_on_an_ambient_sdk_binding(self) -> None:
        self.assertTrue(self.check_document(
            'export const LocalContract = () => <Info>{SDK.sourceVersion}</Info>',
            "snippets/_sdk-contract.mdx",
        ))
        self.assertEqual([], self.check_document(
            'export const LocalContract = ({ sdk }) => <Info>{sdk.sourceVersion}</Info>',
            "snippets/_sdk-contract.mdx",
        ))

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
