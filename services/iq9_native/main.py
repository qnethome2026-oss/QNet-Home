"""Run an embedded MQTT broker and the QHome voice router on IQ9."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from amqtt.broker import Broker


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("qnet.iq9.native")

def broker_config(host: str, port: int) -> dict:
    return {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"{host}:{port}",
                "max_connections": 50,
            },
            "websocket": {
                "type": "ws",
                "bind": f"{host}:{int(os.getenv('QHOME_MQTT_WEBSOCKET_PORT', '9001'))}",
                "max_connections": 20,
            },
        },
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True,
            },
            "amqtt.plugins.sys.broker.BrokerSysPlugin": {
                "sys_interval": 20,
            },
        },
    }


async def run() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_dir = repo_root / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    broker_host = os.getenv("QHOME_MQTT_LISTEN_HOST", "0.0.0.0")
    broker_port = int(os.getenv("QHOME_MQTT_PORT", "1883"))
    broker = Broker(broker_config(broker_host, broker_port))
    await broker.start()
    LOGGER.info("MQTT broker listening on %s:%s", broker_host, broker_port)

    router_env = os.environ.copy()
    router_env.setdefault("QHOME_MQTT_HOST", "127.0.0.1")
    router_env.setdefault("QHOME_MQTT_PORT", str(broker_port))
    router_env.setdefault("QHOME_DEVICE_REGISTRY", str(repo_root / "config" / "home.example.yaml"))
    router_env.setdefault("QHOME_HISTORY_PATH", str(runtime_dir / "announcements.jsonl"))

    router = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "services.iq9_voice_router.main",
        cwd=repo_root,
        env=router_env,
    )
    LOGGER.info("Voice router started with PID %s", router.pid)

    agent_env = os.environ.copy()
    agent_env.setdefault("QNET_MQTT_HOST", "127.0.0.1")
    agent_env.setdefault("QNET_MQTT_PORT", str(broker_port))
    agent_env.setdefault("QNET_SESSIONS_DIR", str(runtime_dir / "sessions"))
    agent = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "agent.engine",
        cwd=repo_root,
        env=agent_env,
    )
    LOGGER.info("Phase-1 agent started with PID %s", agent.pid)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)

    stop_waiter = asyncio.create_task(stop_event.wait())
    router_waiter = asyncio.create_task(router.wait())
    agent_waiter = asyncio.create_task(agent.wait())
    try:
        done, _pending = await asyncio.wait(
            {stop_waiter, router_waiter, agent_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if router_waiter in done and router.returncode:
            raise RuntimeError(f"voice router exited with status {router.returncode}")
        if agent_waiter in done and agent.returncode:
            raise RuntimeError(f"agent exited with status {agent.returncode}")
    finally:
        stop_waiter.cancel()
        for process in (router, agent):
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
        try:
            await broker.shutdown()
        except asyncio.CancelledError:
            # aMQTT may cancel an in-flight QoS acknowledgement during SIGTERM.
            LOGGER.info("MQTT shutdown cancelled an in-flight message")
        LOGGER.info("IQ9 native runtime stopped")


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
