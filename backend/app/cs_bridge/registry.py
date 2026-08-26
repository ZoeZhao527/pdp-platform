from app.cs_bridge.generic import EchoAdapter, GenericHttpAdapter
from app.cs_bridge.protocol import CsPlatformAdapter, CsSession


class CsBridgeRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, CsPlatformAdapter] = {}

    def register(self, adapter: CsPlatformAdapter) -> None:
        self._adapters[adapter.platform] = adapter

    def get(self, platform: str) -> CsPlatformAdapter:
        return self._adapters.get(platform) or self._adapters["generic_http"]


cs_bridge_registry = CsBridgeRegistry()
cs_bridge_registry.register(GenericHttpAdapter())
cs_bridge_registry.register(EchoAdapter())

