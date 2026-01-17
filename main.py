from src import Core
import asyncio

from config.api_config import APIConfig

if __name__ == "__main__":
    core = Core()
    asyncio.run(core.run())
