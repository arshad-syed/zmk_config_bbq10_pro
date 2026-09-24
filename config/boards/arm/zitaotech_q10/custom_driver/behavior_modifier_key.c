/* SPDX-License-Identifier: MIT */

#define DT_DRV_COMPAT zmk_behavior_modifier_key

#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/keymap.h>

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

struct modifier_key_config {
    uint32_t tapping_term_ms;
    struct zmk_behavior_binding key;
};

struct modifier_key_data {
    bool pressed;
    bool locked;
    bool unlocking;
    bool used;
    bool tap_pending;
    uint32_t position;
    int64_t pressed_at;
};

static const struct device *modifier_keys[DT_NUM_INST_STATUS_OKAY(DT_DRV_COMPAT)];
static size_t modifier_key_count;

static int modifier_key_pressed(struct zmk_behavior_binding *binding,
                                struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct modifier_key_config *cfg = dev->config;
    struct modifier_key_data *data = dev->data;

    if (data->pressed) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

    bool second_tap = data->tap_pending && data->position == event.position &&
                      event.timestamp - data->pressed_at <= cfg->tapping_term_ms;
    data->pressed = true;
    data->position = event.position;
    data->pressed_at = event.timestamp;
    data->tap_pending = false;
    data->used = false;

    if (data->locked) {
        /* Unlock on key-down; this press's release must not start another dance. */
        data->locked = false;
        data->unlocking = true;
        return zmk_behavior_invoke_binding(&cfg->key, event, false);
    }

    data->unlocking = false;
    data->locked = second_tap;
    /* The first press is an ordinary modifier immediately. The double-tap
     * window only determines whether the second release leaves it locked.
     */
    return zmk_behavior_invoke_binding(&cfg->key, event, true);
}

static int modifier_key_released(struct zmk_behavior_binding *binding,
                                 struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct modifier_key_config *cfg = dev->config;
    struct modifier_key_data *data = dev->data;

    if (!data->pressed || data->position != event.position) {
        return ZMK_BEHAVIOR_OPAQUE;
    }
    data->pressed = false;
    if (data->unlocking) {
        data->unlocking = false;
        return ZMK_BEHAVIOR_OPAQUE;
    }
    if (data->locked) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

    data->tap_pending = !data->used &&
                        event.timestamp - data->pressed_at <= cfg->tapping_term_ms;
    return zmk_behavior_invoke_binding(&cfg->key, event, false);
}

static int modifier_key_listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *position = as_zmk_position_state_changed(eh);
    const struct zmk_layer_state_changed *layer = as_zmk_layer_state_changed(eh);
    for (size_t i = 0; i < modifier_key_count; i++) {
        struct modifier_key_data *data = modifier_keys[i]->data;
        if (layer || (position && position->state && position->position != data->position)) {
            /* A shortcut or layer change between taps is not a double tap.
             * Existing locks stay active until their own modifier is tapped.
             */
            data->tap_pending = false;
            data->used = true;
        }
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(modifier_key, modifier_key_listener);
ZMK_SUBSCRIPTION(modifier_key, zmk_position_state_changed);
ZMK_SUBSCRIPTION(modifier_key, zmk_layer_state_changed);

static const struct behavior_driver_api modifier_key_api = {
    .binding_pressed = modifier_key_pressed,
    .binding_released = modifier_key_released,
};

static int modifier_key_init(const struct device *dev) {
    modifier_keys[modifier_key_count++] = dev;
    return 0;
}

#define MODIFIER_KEY_INST(n)                                                                       \
    static struct modifier_key_data modifier_key_data_##n;                                         \
    static const struct modifier_key_config modifier_key_config_##n = {                            \
        .tapping_term_ms = DT_INST_PROP(n, tapping_term_ms),                                        \
        .key = ZMK_KEYMAP_EXTRACT_BINDING(0, DT_DRV_INST(n)),                                        \
    };                                                                                            \
    BEHAVIOR_DT_INST_DEFINE(n, modifier_key_init, NULL, &modifier_key_data_##n,                      \
                            &modifier_key_config_##n, POST_KERNEL,                                \
                            CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &modifier_key_api);

DT_INST_FOREACH_STATUS_OKAY(MODIFIER_KEY_INST)
#endif
