# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

from normly_core.graph.domain import Role

from normly_accounts.permissions import CAPABILITIES, MATRIX_ROLES, USER_MANAGEMENT, allows


def test_only_administrators_may_manage_users():
    assert allows(Role.ADMINISTRATOR, USER_MANAGEMENT)
    assert not allows(Role.PUBLISHER, USER_MANAGEMENT)
    assert not allows(Role.USER, USER_MANAGEMENT)


def test_every_capability_names_every_matrix_role():
    for capability in CAPABILITIES:
        assert set(capability.values) == set(MATRIX_ROLES), capability.key


def test_nobody_sees_chats_or_personal_usage_data_of_others():
    by_key = {c.key: c for c in CAPABILITIES}
    for key in ("chats_of_others", "personal_usage_data_of_others"):
        assert set(by_key[key].values.values()) == {"no"}
