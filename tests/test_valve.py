""" Test the normal start of a Switch AC Thermostat """
from unittest.mock import patch, call
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntryState

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components.climate import ClimateEntity, DOMAIN as CLIMATE_DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.versatile_thermostat.base_thermostat import BaseThermostat
from custom_components.versatile_thermostat.thermostat_valve import ThermostatOverValve

from .commons import *  # pylint: disable=wildcard-import, unused-wildcard-import

@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_over_valve_full_start(hass: HomeAssistant, skip_hass_states_is_state):   # pylint: disable=unused-argument
    """Test the normal full start of a thermostat in thermostat_over_switch type"""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TheOverValveMockName",
        unique_id="uniqueId",
        data={
            CONF_NAME: "TheOverValveMockName",
            CONF_THERMOSTAT_TYPE: CONF_THERMOSTAT_VALVE,
            CONF_TEMP_SENSOR: "sensor.mock_temp_sensor",
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.mock_ext_temp_sensor",
            CONF_VALVE: "number.mock_valve",
            CONF_CYCLE_MIN: 5,
            CONF_TEMP_MIN: 15,
            CONF_TEMP_MAX: 30,
            PRESET_ECO + "_temp": 17,
            PRESET_COMFORT + "_temp": 19,
            PRESET_BOOST + "_temp": 21,
            CONF_USE_WINDOW_FEATURE: True,
            CONF_USE_MOTION_FEATURE: True,
            CONF_USE_POWER_FEATURE: True,
            CONF_USE_PRESENCE_FEATURE: True,
            CONF_PROP_FUNCTION: PROPORTIONAL_FUNCTION_TPI,
            CONF_TPI_COEF_INT: 0.3,
            CONF_TPI_COEF_EXT: 0.01,
            CONF_MOTION_SENSOR: "input_boolean.motion_sensor",
            CONF_WINDOW_SENSOR: "binary_sensor.window_sensor",
            CONF_WINDOW_DELAY: 10,
            CONF_MOTION_DELAY: 10,
            CONF_MOTION_OFF_DELAY: 30,
            CONF_MOTION_PRESET: PRESET_COMFORT,
            CONF_NO_MOTION_PRESET: PRESET_ECO,
            CONF_POWER_SENSOR: "sensor.power_sensor",
            CONF_MAX_POWER_SENSOR: "sensor.power_max_sensor",
            CONF_PRESENCE_SENSOR: "person.presence_sensor",
            PRESET_ECO + PRESET_AWAY_SUFFIX + "_temp": 17.1,
            PRESET_COMFORT + PRESET_AWAY_SUFFIX + "_temp": 17.2,
            PRESET_BOOST + PRESET_AWAY_SUFFIX + "_temp": 17.3,
            CONF_PRESET_POWER: 10,
            CONF_MINIMAL_ACTIVATION_DELAY: 30,
            CONF_SECURITY_DELAY_MIN: 5,
            CONF_SECURITY_MIN_ON_PERCENT: 0.3,
            CONF_DEVICE_POWER: 100,
            CONF_AC_MODE: False
        },
    )

    tz = get_tz(hass)  # pylint: disable=invalid-name
    now: datetime = datetime.now(tz=tz)

    with patch(
        "custom_components.versatile_thermostat.base_thermostat.BaseThermostat.send_event"
    ) as mock_send_event:
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED

        def find_my_entity(entity_id) -> ClimateEntity:
            """Find my new entity"""
            component: EntityComponent[ClimateEntity] = hass.data[CLIMATE_DOMAIN]
            for entity in component.entities:
                if entity.entity_id == entity_id:
                    return entity

        # The name is in the CONF and not the title of the entry
        entity: BaseThermostat = find_my_entity("climate.theovervalvemockname")

        assert entity
        assert isinstance(entity, ThermostatOverValve)

        assert entity.name == "TheOverValveMockName"
        assert entity.is_over_climate is False
        assert entity.is_over_switch is False
        assert entity.is_over_valve is True
        assert entity.ac_mode is False
        assert entity.hvac_mode is HVACMode.OFF
        assert entity.hvac_action is HVACAction.OFF
        assert entity.hvac_modes == [HVACMode.HEAT, HVACMode.OFF]
        assert entity.target_temperature == entity.min_temp
        assert entity.preset_modes == [
            PRESET_NONE,
            PRESET_ECO,
            PRESET_COMFORT,
            PRESET_BOOST,
            PRESET_ACTIVITY,
        ]
        assert entity.preset_mode is PRESET_NONE
        assert entity._security_state is False             # pylint: disable=protected-access
        assert entity._window_state is None       # pylint: disable=protected-access
        assert entity._motion_state is None       # pylint: disable=protected-access
        assert entity._presence_state is None       # pylint: disable=protected-access
        assert entity._prop_algorithm is not None       # pylint: disable=protected-access

        # should have been called with EventType.PRESET_EVENT and EventType.HVAC_MODE_EVENT
        assert mock_send_event.call_count == 2

        mock_send_event.assert_has_calls(
            [
                call.send_event(EventType.PRESET_EVENT, {"preset": PRESET_NONE}),
                call.send_event(
                    EventType.HVAC_MODE_EVENT,
                    {"hvac_mode": HVACMode.OFF},
                ),
            ]
        )

        # Select a hvacmode, presence and preset
        await entity.async_set_hvac_mode(HVACMode.COOL)
        assert entity.hvac_mode is HVACMode.COOL

        event_timestamp = now - timedelta(minutes=4)
        await send_presence_change_event(entity, True, False, event_timestamp)
        assert entity._presence_state == STATE_ON   # pylint: disable=protected-access

        await entity.async_set_hvac_mode(HVACMode.COOL)
        assert entity.hvac_mode is HVACMode.COOL

        await entity.async_set_preset_mode(PRESET_COMFORT)
        assert entity.preset_mode is PRESET_COMFORT
        assert entity.target_temperature == 23

        # switch to Eco
        await entity.async_set_preset_mode(PRESET_ECO)
        assert entity.preset_mode is PRESET_ECO
        assert entity.target_temperature == 25

        # Unset the presence
        event_timestamp = now - timedelta(minutes=3)
        await send_presence_change_event(entity, False, True, event_timestamp)
        assert entity._presence_state == STATE_OFF   # pylint: disable=protected-access
        assert entity.target_temperature == 27 # eco_ac_away

        # Open a window
        with patch(
            "homeassistant.helpers.condition.state", return_value=True
        ):
            event_timestamp = now - timedelta(minutes=2)
            try_condition = await send_window_change_event(entity, True, False, event_timestamp)

            # Confirme the window event
            await try_condition(None)

            assert entity.hvac_mode is HVACMode.OFF
            assert entity.hvac_action is HVACAction.OFF
            assert entity.target_temperature == 27 # eco_ac_away

        # Close a window
        with patch(
            "homeassistant.helpers.condition.state", return_value=True
        ):
            event_timestamp = now - timedelta(minutes=2)
            try_condition = await send_window_change_event(entity, False, True, event_timestamp)

            # Confirme the window event
            await try_condition(None)

            assert entity.hvac_mode is HVACMode.COOL
            assert (entity.hvac_action is HVACAction.OFF or entity.hvac_action is HVACAction.IDLE)
            assert entity.target_temperature == 27 # eco_ac_away
