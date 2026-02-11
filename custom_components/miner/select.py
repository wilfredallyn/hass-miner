"""A selector for the miner's mining mode."""
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity
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
    if (
        coordinator.miner.supports_power_modes
        and not coordinator.miner.supports_autotuning
    ):
        entities.append(MinerPowerModeSwitch(coordinator=coordinator))
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
    """A selector for the miner's LuxOS preset."""

    def __init__(self, coordinator: MinerCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self.coordinator.data['mac']}-preset"

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return f"{self.coordinator.config_entry.title} preset"

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
        """Return the currently active preset name."""
        config: pyasic.MinerConfig | None = self.coordinator.data["config"]
        if config is None:
            return None
        try:
            name = config.mining_mode.active_preset.name
            presets = config.mining_mode.available_presets
            valid = {p.name for p in presets if p.name is not None}
            return name if name in valid else None
        except AttributeError:
            return None

    @property
    def options(self) -> list[str]:
        """Return the list of available preset names."""
        config: pyasic.MinerConfig | None = self.coordinator.data["config"]
        if config is None:
            return []
        try:
            presets = config.mining_mode.available_presets
            return [p.name for p in presets if p.name is not None]
        except AttributeError:
            return []

    async def async_select_option(self, option: str) -> None:
        """Change the active preset. Raises HomeAssistantError on failure."""
        try:
            result = await self.coordinator.miner.set_profile(option)
        except Exception as err:
            raise HomeAssistantError(f"Failed to set preset: {err}") from err
        if result is False:
            raise HomeAssistantError(f"Miner rejected preset change to {option}")
        await self.coordinator.async_request_refresh()
