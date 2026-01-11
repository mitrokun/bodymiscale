"""Config flow to configure the bodymiscale integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_MODE, CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BIRTHDAY,
    CONF_GENDER,
    CONF_HEIGHT,
    CONF_SENSOR_IMPEDANCE,
    CONF_SENSOR_WEIGHT,
    CONF_WEIGHT_MIN,
    CONF_WEIGHT_MAX,
    CONSTRAINT_HEIGHT_MAX,
    CONSTRAINT_HEIGHT_MIN,
    CONSTRAINT_WEIGHT_MAX,
    CONSTRAINT_WEIGHT_MIN, 
    DOMAIN,
    MAX,
    MIN,
)
from .models import Gender


@callback  # type: ignore[misc]
def _get_options_schema(
    defaults: dict[str, Any] | MappingProxyType[str, Any],
) -> vol.Schema:
    """Return options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_HEIGHT,
                description=(
                    {"suggested_value": defaults[CONF_HEIGHT]}
                    if CONF_HEIGHT in defaults
                    else None
                ),
            ): selector( # Здесь можно тоже добавить vol.All(vol.Coerce(float), selector(...)) для единообразия
                {
                    "number": {
                        MIN: CONSTRAINT_HEIGHT_MIN,
                        MAX: CONSTRAINT_HEIGHT_MAX,
                        CONF_UNIT_OF_MEASUREMENT: "cm",
                        CONF_MODE: "box",
                    }
                }
            ),

            # --- НАЧАЛО ИЗМЕНЕНИЯ ---
            vol.Optional(
                CONF_WEIGHT_MIN,
                description=(
                    {"suggested_value": defaults.get(CONF_WEIGHT_MIN)}
                ),
                default=defaults.get(CONF_WEIGHT_MIN, 0.0), # Используем float для значения по умолчанию
            ): vol.All(
                vol.Coerce(float), # Шаг 1: Преобразовать значение в float
                selector(          # Шаг 2: Указать, как отображать поле в UI
                    {
                        "number": {
                            MIN: 0.0, # Используем float
                            MAX: float(CONSTRAINT_WEIGHT_MAX), # Используем float
                            CONF_UNIT_OF_MEASUREMENT: "kg",
                            CONF_MODE: "box",
                            "step": 0.1, # Добавим шаг для дробных чисел
                        }
                    }
                )
            ),
            
            vol.Optional(
                CONF_WEIGHT_MAX,
                description=(
                    {"suggested_value": defaults.get(CONF_WEIGHT_MAX)}
                ),
                default=defaults.get(CONF_WEIGHT_MAX, float(CONSTRAINT_WEIGHT_MAX)), # Используем float
            ): vol.All(
                vol.Coerce(float), # Шаг 1: Преобразовать значение в float
                selector(          # Шаг 2: Указать, как отображать поле в UI
                    {
                        "number": {
                            MIN: 0.0, # Используем float
                            MAX: float(CONSTRAINT_WEIGHT_MAX), # Используем float
                            CONF_UNIT_OF_MEASUREMENT: "kg",
                            CONF_MODE: "box",
                            "step": 0.1, # Добавим шаг для дробных чисел
                        }
                    }
                )
            ),
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            vol.Required(
                CONF_SENSOR_WEIGHT,
                description=(
                    {"suggested_value": defaults[CONF_SENSOR_WEIGHT]}
                    if CONF_SENSOR_WEIGHT in defaults
                    else None
                ),
            ): selector({"entity": {"domain": ["sensor", "input_number", "number"]}}),
            vol.Optional(
                CONF_SENSOR_IMPEDANCE,
                description=(
                    {"suggested_value": defaults[CONF_SENSOR_IMPEDANCE]}
                    if CONF_SENSOR_IMPEDANCE in defaults
                    else None
                ),
            ): selector({"entity": {"domain": ["sensor", "input_number", "number"]}}),
        }
    )


class BodyMiScaleFlowHandler(ConfigFlow, domain=DOMAIN):  # type: ignore[misc, call-arg]
    """Config flow for bodymiscale."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._data: dict[str, str] = {}

    @staticmethod
    @callback  # type: ignore[misc]
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BodyMiScaleOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BodyMiScaleOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                cv.date(user_input[CONF_BIRTHDAY])
            except vol.Invalid:
                errors[CONF_BIRTHDAY] = "invalid_date"

            if not errors:
                self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})
                self._data = user_input
                return await self.async_step_options()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, vol.UNDEFINED)
                    ): str,
                    vol.Required(
                        CONF_BIRTHDAY,
                        default=user_input.get(CONF_BIRTHDAY, vol.UNDEFINED),
                    ): selector({"text": {"type": "date"}}),
                    vol.Required(
                        CONF_GENDER, default=user_input.get(CONF_GENDER, vol.UNDEFINED)
                    ): vol.In({gender: gender.value for gender in Gender}),
                }
            ),
        )

    # --- НАЧАЛО ИЗМЕНЕННОГО МЕТОДА ---
    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step options."""
        errors = {}
        if user_input is not None:
            # Валидация роста
            if user_input.get(CONF_HEIGHT, 0) > CONSTRAINT_HEIGHT_MAX:
                errors[CONF_HEIGHT] = "height_limit"
            elif user_input.get(CONF_HEIGHT, 0) < CONSTRAINT_HEIGHT_MIN:
                errors[CONF_HEIGHT] = "height_low"

            # Валидация диапазона веса
            # Мы используем .get() для безопасного доступа, на случай если ключей нет
            weight_min = user_input.get(CONF_WEIGHT_MIN, 0)
            weight_max = user_input.get(CONF_WEIGHT_MAX, CONSTRAINT_WEIGHT_MAX)
            
            # Проверяем, что минимальное значение меньше максимального
            if weight_min >= weight_max:
                # 'base' используется для отображения общей ошибки, не привязанной к конкретному полю
                errors["base"] = "weight_range_invalid"

            # Если ошибок нет, создаем запись конфигурации
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data, options=user_input
                )

        # Если это первый показ формы (user_input is None) или были ошибки,
        # показываем форму снова.
        # Если user_input не None (т.е. была ошибка), он будет использован для предзаполнения полей.
        # Если user_input is None, создается пустой словарь.
        current_data = user_input or {}
        
        return self.async_show_form(
            step_id="options",
            data_schema=_get_options_schema(current_data),
            errors=errors,
        )
    # --- КОНЕЦ ИЗМЕНЕННОГО МЕТОДА ---


class BodyMiScaleOptionsFlowHandler(OptionsFlow):  # type: ignore[misc]
    """Handle Body mi scale options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Body mi scale options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Body mi scale options."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._config_entry.title,
                data=user_input,
            )

        user_input = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=_get_options_schema(user_input),
        )
