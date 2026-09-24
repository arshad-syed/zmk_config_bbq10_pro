/* SPDX-License-Identifier: MIT */

/* Native-only host transport: inspect the actual report after modifier masking.
 * Production behavior, keymap, HID state, and event processing remain unchanged.
 */
#include <zephyr/sys/printk.h>
#include <zephyr/kernel.h>
#include <zmk/hid.h>

int __wrap_zmk_endpoints_send_report(uint16_t usage_page) {
    if (usage_page != 0x07) {
        return 0;
    }
    const struct zmk_hid_keyboard_report *report = zmk_hid_get_keyboard_report();
    char line[1024];
    int used = snprintk(line, sizeof(line), "TEST_HID t=%lld mods=%02x keys=",
                       (long long)k_uptime_get(), report->body.modifiers);
    for (uint16_t key = 4; key < 0xE0; key++) {
        if (zmk_hid_keyboard_is_pressed(key)) {
            used += snprintk(line + used, sizeof(line) - used, "%02x ", key);
        }
    }
    printk("%s\n", line);
    return 0;
}
