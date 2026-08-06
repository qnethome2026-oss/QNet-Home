# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Room-node services (DESIGN.md §5).

Plain Python services on Ubuntu, run under systemd on the Ventuno Q. They know
nothing about skills or the LLM: they sense, they speak, they publish MQTT.
"""
