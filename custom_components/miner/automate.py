from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.config_entries import ConfigEntry

GRID_CONSUMPTION_ENTITY = "sensor.pw_grid_consumption"
MINER_POWER_LIMIT_ENTITY = "number.miner_power_limit"
HIGH_POWER_THRESHOLD = 0
LOW_POWER_THRESHOLD = 0
HIGH_POWER_LIMIT = 500
LOW_POWER_LIMIT = 100
TIME_THRESHOLD = timedelta(minutes=30)


class PowerAdjustment:
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self.last_high_power_time = None
        self.last_low_power_time = None
        self.automation_active = False
        self._remove_listener = None

    async def async_setup(self):
        self.automation_active = self.config_entry.options.get("automation_active", False)
        if self.automation_active:
            await self._start_automation()

    async def _start_automation(self):
        self._remove_listener = async_track_state_change_event(
            self.hass, GRID_CONSUMPTION_ENTITY, self.handle_grid_consumption_change
        )

    async def _stop_automation(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def toggle_automation(self, active: bool):
        self.automation_active = active
        if active:
            await self._start_automation()
        else:
            await self._stop_automation()

        # Update config entry
        new_options = dict(self.config_entry.options)
        new_options["automation_active"] = active
        self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

    async def handle_grid_consumption_change(self, event):
        new_state = event.data.get('new_state')
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        grid_consumption = float(new_state.state)
        current_time = datetime.now()

        if grid_consumption > HIGH_POWER_THRESHOLD:
            if self.last_high_power_time is None:
                self.last_high_power_time = current_time
            elif current_time - self.last_high_power_time >= TIME_THRESHOLD:
                await self.set_miner_power(HIGH_POWER_LIMIT)
            self.last_low_power_time = None
        elif grid_consumption <= LOW_POWER_THRESHOLD:
            if self.last_low_power_time is None:
                self.last_low_power_time = current_time
            elif current_time - self.last_low_power_time >= TIME_THRESHOLD:
                await self.set_miner_power(LOW_POWER_LIMIT)
            self.last_high_power_time = None
        else:
            self.last_high_power_time = None
            self.last_low_power_time = None

    async def set_miner_power(self, power):
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": MINER_POWER_LIMIT_ENTITY, "value": power},
            blocking=True
        )

async def async_setup_power_adjustment(hass: HomeAssistant, config_entry: ConfigEntry):
    power_adjustment = PowerAdjustment(hass, config_entry)
    await power_adjustment.async_setup()
    return power_adjustment