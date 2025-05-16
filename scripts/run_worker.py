#!/usr/bin/env python
import os
import sys
import asyncio
from arq.worker import Worker

from worker.gltf_worker import WorkerSettings

async def main():
    """Run the ARQ worker"""
    print("Starting ARQ worker...")
    worker = Worker(WorkerSettings)
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 