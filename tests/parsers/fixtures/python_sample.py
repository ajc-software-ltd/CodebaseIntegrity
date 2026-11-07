"""Python extraction fixture: classes, methods, properties, decorators,
nested functions and nested classes."""

import asyncio
from abc import ABC, abstractmethod


class Engine(ABC):
    """Base engine."""

    def __init__(self, name):
        self.name = name

    def __del__(self):
        pass

    @property
    def status(self):
        return "ok"

    @status.setter
    def status(self, value):
        pass

    @staticmethod
    def create(name):
        return Engine(name)

    @classmethod
    def default(cls):
        return cls("default")

    @abstractmethod
    def run(self):
        raise NotImplementedError


class AudioEngine(Engine, Mixin):
    class Device:
        def open(self):
            def inner():
                return 1
            return inner()

    def __init__(self, name, device):
        super().__init__(name)
        self.device = device

    async def start(self):
        await asyncio.sleep(0)


@app.route("/health")
def health_check():
    return {"ok": True}


def outer():
    def nested():
        return 2
    return nested
