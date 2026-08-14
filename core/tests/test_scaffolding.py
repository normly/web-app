# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import normly_core


def test_package_is_importable():
    assert normly_core is not None
