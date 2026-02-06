"""A selector for the miner's mining mode and profile/preset."""
from __future__ import annotations

import logging
from importlib.metadata import version

from .const import PYASIC_VERSION

try:
    import pyasic

    if not version("pyasic") == PYASIC_VERSION:
        raise ImportError
except ImportError:
    from .patch import install_package

    install_package(f"pyasic=={PYASIC_VERSION}")
    import pyasic

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyasic.config.mining import MiningModeHPM, MiningModeLPM, MiningModeNormal

from custom_components.miner import DOMAIN, MinerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: MinerCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    created = set()

    @callback
    def _create_entity(key: str):
        """Create a sensor entity."""
        created.add(key)

    await coordinator.async_config_entry_first_refresh()

    entities = []

    # Power mode selector for miners that support power modes but not autotuning
    if (
        coordinator.miner.supports_power_modes
        and not coordinator.miner.supports_autotuning
    ):
        entities.append(MinerPowerModeSwitch(coordinator=coordinator))

    # Profile/preset selector for miners that support presets (LuxOS, Vnish, etc.)
    if coordinator.miner.supports_presets:
        entities.append(MinerPresetSelect(coordinator=coordinator))

    if entities:
        async_add_entities(entities)


class MinerPowerModeSwitch(CoordinatorEntity[MinerCoordinator], SelectEntity):
    """A selector for the miner's miner mode."""

    def __init__(
        self,
        coordinator: MinerCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data['mac']}-power-mode"

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return f"{self.coordinator.config_entry.title} power mode"

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return device info."""
        return entity.DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["mac"])},
            manufacturer=self.coordinator.data["make"],
            model=self.coordinator.data["model"],
            sw_version=self.coordinator.data["fw_ver"],
            name=f"{self.coordinator.config_entry.title}",
        )

    @property
    def current_option(self) -> str | None:
        """The current option selected with the select."""
        config: pyasic.MinerConfig = self.coordinator.data["config"]
        return str(config.mining_mode.mode).title()

    @property
    def options(self) -> list[str]:
        """The allowed options for the selector."""
        return ["Normal", "High", "Low"]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        option_map = {
            "High": MiningModeHPM,
            "Normal": MiningModeNormal,
            "Low": MiningModeLPM,
        }
        cfg = await self.coordinator.miner.get_config()
        cfg.mining_mode = option_map[option]()
        await self.coordinator.miner.send_config(cfg)


class MinerPresetSelect(CoordinatorEntity[MinerCoordinator], SelectEntity):
    """A selector for the miner's profile/preset (LuxOS, Vnish, etc.)."""

    def __init__(
        self,
        coordinator: MinerCoordinator,
    ) -> None:
        """Initialize the preset selector."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data['mac']}-preset"

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return f"{self.coordinator.config_entry.title} Profile"

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return device info."""
        return entity.DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["mac"])},
            connections={
                ("ip", self.coordinator.data["ip"]),
                (device_registry.CONNECTION_NETWORK_MAC, self.coordinator.data["mac"]),
            },
            configuration_url=f"http://{self.coordinator.data['ip']}",
            manufacturer=self.coordinator.data["make"],
            model=self.coordinator.data["model"],
            sw_version=self.coordinator.data["fw_ver"],
            name=f"{self.coordinator.config_entry.title}",
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently active preset name."""
        config = self.coordinator.data.get("config")
        if config is None:
            return None
        try:
            if hasattr(config.mining_mode, "active_preset"):
                preset = config.mining_mode.active_preset
                if preset and preset.name:
                    return preset.name
        except (AttributeError, TypeError):
            pass
        return None

    @property
    def options(self) -> list[str]:
        """Return list of available preset names."""
        config = self.coordinator.data.get("config")
        if config is None:
            return []
        try:
            if hasattr(config.mining_mode, "available_presets"):
                presets = config.mining_mode.available_presets
                if presets:
                    return [p.name for p in presets if p.name]
        except (AttributeError, TypeError):
            pass
        return []

    async def async_select_option(self, option: str) -> None:
        """Change the selected preset/profile."""
        miner = self.coordinator.miner

        _LOGGER.debug(
            f"{self.coordinator.config_entry.title}: setting profile to {option}."
        )

        if not miner.supports_presets:
            raise TypeError(
                f"{self.coordinator.config_entry.title}: Presets not supported."
            )

        # Use profileset RPC command for LuxOS
        if hasattr(miner.rpc, "profileset"):
            result = await miner.rpc.profileset(option)
            _LOGGER.debug(f"profileset result: {result}")
        else:
            # Fallback: set via config for other firmware (e.g., Vnish)
            cfg = await miner.get_config()
            if hasattr(cfg.mining_mode, "active_preset"):
                # Find the preset object by name
                for preset in getattr(cfg.mining_mode, "available_presets", []):
                    if preset.name == option:
                        cfg.mining_mode.active_preset = preset
                        break
                await miner.send_config(cfg)

        # Request coordinator refresh to update state
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available and len(self.options) > 0
