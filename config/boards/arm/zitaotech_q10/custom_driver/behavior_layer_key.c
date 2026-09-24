/* SPDX-License-Identifier: MIT */

#define DT_DRV_COMPAT zmk_behavior_layer_key

#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/keycode_state_changed.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/keymap.h>
#include <zmk/keys.h>
#include "behavior_layer_key.h"

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

enum layer_mode { LAYER_OFF, LAYER_ONCE, LAYER_PERSISTENT };

struct layer_key_config {
    uint8_t layer;
    int parent_layer;
    uint32_t tapping_term_ms;
    uint32_t release_after_ms;
};

struct layer_key_data {
    const struct device *dev;
    enum layer_mode mode;
    bool pressed;
    bool used;
    bool tap_pending;
    uint32_t position;
    int64_t pressed_at;
    int64_t expires_at;
    struct k_work_delayable expire_work;
};

static const struct device *layer_keys[DT_NUM_INST_STATUS_OKAY(DT_DRV_COMPAT)];
static size_t layer_key_count;

static bool persistent_parent(int layer) {
    for (size_t i = 0; i < layer_key_count; i++) {
        const struct layer_key_config *cfg = layer_keys[i]->config;
        const struct layer_key_data *data = layer_keys[i]->data;
        if (cfg->layer == layer && data->mode == LAYER_PERSISTENT &&
            zmk_keymap_layer_active(layer)) {
            return true;
        }
    }
    return false;
}

static void clear_state(struct layer_key_data *data) {
    k_work_cancel_delayable(&data->expire_work);
    data->mode = LAYER_OFF;
    data->pressed = false;
    data->used = false;
    data->tap_pending = false;
}

static void leave_layer(const struct device *dev, bool cascade) {
    const struct layer_key_config *cfg = dev->config;
    clear_state(dev->data);
    for (size_t i = 0; i < layer_key_count; i++) {
        const struct layer_key_config *child = layer_keys[i]->config;
        const struct layer_key_data *child_data = layer_keys[i]->data;
        if (cascade && child->parent_layer == cfg->layer && child_data->mode != LAYER_OFF) {
            leave_layer(layer_keys[i], true);
        }
    }
    zmk_keymap_layer_deactivate(cfg->layer);
}

static bool child_active(uint8_t layer) {
    for (size_t i = 0; i < layer_key_count; i++) {
        const struct layer_key_config *cfg = layer_keys[i]->config;
        const struct layer_key_data *data = layer_keys[i]->data;
        if (cfg->parent_layer == layer && !data->pressed && zmk_keymap_layer_active(cfg->layer)) {
            return true;
        }
    }
    return false;
}

static void arm_expiry(struct layer_key_data *data, int64_t timestamp) {
    const struct layer_key_config *cfg = data->dev->config;
    data->expires_at = timestamp + cfg->release_after_ms;
    k_work_reschedule(&data->expire_work,
                      K_MSEC(MAX(1, data->expires_at - k_uptime_get())));
}

static void enter_layer(const struct device *dev, enum layer_mode mode) {
    const struct layer_key_config *cfg = dev->config;
    struct layer_key_data *data = dev->data;
    /* Keep a held or locked parent. A released one-shot parent must not
     * leave an old expiry timer underneath the new child layer.
     */
    if (cfg->parent_layer >= 0 && !persistent_parent(cfg->parent_layer) &&
        !bbq_layer_key_is_held(cfg->parent_layer)) {
        for (size_t i = 0; i < layer_key_count; i++) {
            const struct layer_key_config *parent = layer_keys[i]->config;
            if (parent->layer == cfg->parent_layer) {
                leave_layer(layer_keys[i], false);
            }
        }
    }
    for (size_t i = 0; i < layer_key_count; i++) {
        const struct layer_key_config *parent = layer_keys[i]->config;
        struct layer_key_data *parent_data = layer_keys[i]->data;
        if (parent->layer == cfg->parent_layer && parent_data->pressed) {
            parent_data->used = true;
            parent_data->tap_pending = false;
        }
    }
    k_work_cancel_delayable(&data->expire_work);
    data->mode = mode;
    data->tap_pending = false;
    zmk_keymap_layer_activate(cfg->layer);
}

/* Queried by the SYM Command/0 binding. A locked layer is not a held chord. */
bool bbq_layer_key_is_held(uint8_t layer) {
    for (size_t i = 0; i < layer_key_count; i++) {
        const struct layer_key_config *cfg = layer_keys[i]->config;
        const struct layer_key_data *data = layer_keys[i]->data;
        if (cfg->layer == layer && data->pressed && data->mode == LAYER_ONCE) {
            return true;
        }
    }
    return false;
}

static void one_shot_timeout(struct k_work *work) {
    struct layer_key_data *data =
        CONTAINER_OF(k_work_delayable_from_work(work), struct layer_key_data, expire_work);
    if (data->mode != LAYER_ONCE || data->pressed) {
        return;
    }
    int64_t remaining = data->expires_at - k_uptime_get();
    if (remaining > 0) {
        k_work_reschedule(&data->expire_work, K_MSEC(remaining));
    } else {
        leave_layer(data->dev, false);
    }
}

static int layer_key_pressed(struct zmk_behavior_binding *binding,
                              struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct layer_key_config *cfg = dev->config;
    struct layer_key_data *data = dev->data;

    /* A second tap upgrades the first tap's live one-shot instead of exiting it. */
    if (data->mode == LAYER_ONCE && !data->pressed && data->tap_pending &&
        data->position == event.position &&
        event.timestamp - data->pressed_at <= cfg->tapping_term_ms) {
        enter_layer(dev, LAYER_PERSISTENT);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    if (zmk_keymap_layer_active(cfg->layer) || child_active(cfg->layer)) {
        leave_layer(dev, true);
        return ZMK_BEHAVIOR_OPAQUE;
    }

    /* Activate on press so rolling into a symbol before release still works.
     * A held layer stays active for the entire chord, however long the hold.
     */
    enter_layer(dev, LAYER_ONCE);
    data->tap_pending = true;
    data->position = event.position;
    data->pressed_at = event.timestamp;
    data->pressed = true;
    data->used = false;
    return ZMK_BEHAVIOR_OPAQUE;
}

static int layer_key_released(struct zmk_behavior_binding *binding,
                               struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct layer_key_config *cfg = dev->config;
    struct layer_key_data *data = dev->data;
    if (!data->pressed || data->position != event.position) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

    data->pressed = false;
    if (data->mode == LAYER_PERSISTENT) {
        return ZMK_BEHAVIOR_OPAQUE;
    }
    if (data->used || event.timestamp - data->pressed_at >= cfg->tapping_term_ms) {
        leave_layer(dev, false);
    } else {
        arm_expiry(data, event.timestamp);
    }
    return ZMK_BEHAVIOR_OPAQUE;
}

static int layer_key_listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *position = as_zmk_position_state_changed(eh);
    if (position && position->state) {
        for (size_t i = 0; i < layer_key_count; i++) {
            struct layer_key_data *data = layer_keys[i]->data;
            if (position->position != data->position) {
                /* Even a modifier unlock or a firmware-only action separates
                 * two taps. It does not consume a released one-shot layer.
                 */
                data->tap_pending = false;
            }
        }
    }
    const struct zmk_keycode_state_changed *key = as_zmk_keycode_state_changed(eh);
    if (key && key->state) {
        for (size_t i = 0; i < layer_key_count; i++) {
            struct layer_key_data *data = layer_keys[i]->data;
            data->tap_pending = false;
            if (data->mode == LAYER_ONCE && !is_mod(key->usage_page, key->keycode)) {
                if (data->pressed) {
                    data->used = true;
                } else {
                    /* A released one-shot ends on the first eligible key. */
                    leave_layer(layer_keys[i], false);
                }
            }
        }
    }
    const struct zmk_layer_state_changed *layer = as_zmk_layer_state_changed(eh);
    if (layer && !layer->state) {
        for (size_t i = 0; i < layer_key_count; i++) {
            const struct layer_key_config *cfg = layer_keys[i]->config;
            const struct layer_key_data *data = layer_keys[i]->data;
            if (cfg->layer == layer->layer && data->mode != LAYER_OFF) {
                leave_layer(layer_keys[i], true);
            }
        }
    }
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(layer_key, layer_key_listener);
ZMK_SUBSCRIPTION(layer_key, zmk_keycode_state_changed);
ZMK_SUBSCRIPTION(layer_key, zmk_layer_state_changed);
ZMK_SUBSCRIPTION(layer_key, zmk_position_state_changed);

static const struct behavior_driver_api layer_key_api = {
    .binding_pressed = layer_key_pressed,
    .binding_released = layer_key_released,
};

static int layer_key_init(const struct device *dev) {
    struct layer_key_data *data = dev->data;
    data->dev = dev;
    k_work_init_delayable(&data->expire_work, one_shot_timeout);
    layer_keys[layer_key_count++] = dev;
    return 0;
}

#define LAYER_KEY_INST(n)                                                                           \
    static struct layer_key_data layer_key_data_##n;                                               \
    static const struct layer_key_config layer_key_config_##n = {                                   \
        .layer = DT_INST_PROP(n, layer),                                                           \
        .parent_layer = DT_INST_PROP(n, parent_layer),                                              \
        .tapping_term_ms = DT_INST_PROP(n, tapping_term_ms),                                        \
        .release_after_ms = DT_INST_PROP(n, release_after_ms),                                      \
    };                                                                                            \
    BEHAVIOR_DT_INST_DEFINE(n, layer_key_init, NULL, &layer_key_data_##n, &layer_key_config_##n,      \
                            POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &layer_key_api);

DT_INST_FOREACH_STATUS_OKAY(LAYER_KEY_INST)
#endif
