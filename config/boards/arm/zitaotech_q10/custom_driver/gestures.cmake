# Compile the same gesture implementation in firmware and native HID checks.
zephyr_library_sources(
  ${CMAKE_CURRENT_LIST_DIR}/behavior_layer_key.c
  ${CMAKE_CURRENT_LIST_DIR}/behavior_modifier_key.c
  ${CMAKE_CURRENT_LIST_DIR}/behavior_layer_modifier.c
)
