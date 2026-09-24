/* SPDX-License-Identifier: MIT */

#define DT_DRV_COMPAT zmk_behavior_layer_modifier

#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/keymap.h>
#include "behavior_layer_key.h"

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

struct layer_modifier_config {
    uint8_t layer;
    struct zmk_behavior_binding bindings[2];
};

struct layer_modifier_data {
    uint8_t selected;
    bool pressed;
};

static int layer_modifier_pressed(struct zmk_behavior_binding *binding,
                                  struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct layer_modifier_config *cfg = dev->config;
    struct layer_modifier_data *data = dev->data;
    data->selected = bbq_layer_key_is_held(cfg->layer) ? 0 : 1;
    data->pressed = true;
    return zmk_behavior_invoke_binding(&cfg->bindings[data->selected], event, true);
}

static int layer_modifier_released(struct zmk_behavior_binding *binding,
                                   struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct layer_modifier_config *cfg = dev->config;
    struct layer_modifier_data *data = dev->data;
    if (!data->pressed) {
        return ZMK_BEHAVIOR_OPAQUE;
    }
    data->pressed = false;
    /* Release the selected child even if SYM was released before this key. */
    return zmk_behavior_invoke_binding(&cfg->bindings[data->selected], event, false);
}

static const struct behavior_driver_api layer_modifier_api = {
    .binding_pressed = layer_modifier_pressed,
    .binding_released = layer_modifier_released,
};

#define LAYER_MODIFIER_INST(n)                                                                     \
    static struct layer_modifier_data layer_modifier_data_##n;                                     \
    static const struct layer_modifier_config layer_modifier_config_##n = {                        \
        .layer = DT_INST_PROP(n, layer),                                                           \
        .bindings = {ZMK_KEYMAP_EXTRACT_BINDING(0, DT_DRV_INST(n)),                                  \
                     ZMK_KEYMAP_EXTRACT_BINDING(1, DT_DRV_INST(n))},                                \
    };                                                                                            \
    BEHAVIOR_DT_INST_DEFINE(n, NULL, NULL, &layer_modifier_data_##n,                                 \
                            &layer_modifier_config_##n, POST_KERNEL,                              \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &layer_modifier_api);

DT_INST_FOREACH_STATUS_OKAY(LAYER_MODIFIER_INST)
#endif
