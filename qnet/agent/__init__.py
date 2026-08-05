# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The brain: the engine, the rails, and the LLM client (DESIGN.md §5, §6, §10).

Runs on the IQ-9075. Talks to the world over MQTT only - it never calls the
speech service directly; the node's voice adapter does that.
"""
