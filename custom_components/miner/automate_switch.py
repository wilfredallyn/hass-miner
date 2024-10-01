from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

class PowerAutomationSwitch(SwitchEntity):
    def __init__(self, power_adjustment, config_entry):
        self._power_adjustment = power_adjustment
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_power_automation"
        self._attr_name = "Power Automation"

    @property
    def is_on(self):
        return self._power_adjustment.automation_active

    async def async_turn_on(self, **kwargs):
        await self._power_adjustment.toggle_automation(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._power_adjustment.toggle_automation(False)
        self.async_write_ha_state()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    power_adjustment = hass.data[DOMAIN][entry.entry_id]["power_adjustment"]
    async_add_entities([PowerAutomationSwitch(power_adjustment, entry)])