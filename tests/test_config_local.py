# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The gitignored ``house.local.yaml`` overlay: secrets stay out of the repo,
and the merge semantics (dicts deepen, lists replace) hold - a real contacts
list must displace the template's TODO entry, never append to it."""

from qnet.agent.__main__ import load_config


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_no_local_file_loads_template_verbatim(tmp_path):
    _write(tmp_path / "house.yaml", "telegram_bot_token: 'TODO'\nmqtt: {port: 1883}\n")
    config = load_config(str(tmp_path / "house.yaml"))
    assert config["telegram_bot_token"] == "TODO"
    assert config["mqtt"]["port"] == 1883


def test_local_overlay_wins_and_dicts_merge(tmp_path):
    _write(tmp_path / "house.yaml",
           "telegram_bot_token: 'TODO'\nmqtt: {host: '127.0.0.1', port: 1883}\n")
    _write(tmp_path / "house.local.yaml",
           "telegram_bot_token: 'real-token'\nmqtt: {port: 11883}\n")
    config = load_config(str(tmp_path / "house.yaml"))
    assert config["telegram_bot_token"] == "real-token"
    # dict merge is deep: the overlay's port lands, the template's host survives
    assert config["mqtt"] == {"host": "127.0.0.1", "port": 11883}


def test_lists_replace_wholesale(tmp_path):
    _write(tmp_path / "house.yaml",
           "contacts:\n  - {name: 'Sarah', telegram_chat_id: 'TODO'}\n")
    _write(tmp_path / "house.local.yaml",
           "contacts:\n  - {name: 'Sarah', telegram_chat_id: '12345'}\n")
    config = load_config(str(tmp_path / "house.yaml"))
    assert config["contacts"] == [{"name": "Sarah", "telegram_chat_id": "12345"}]
