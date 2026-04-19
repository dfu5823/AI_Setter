# Kilter DB Exploration Report

Database: `/Users/danfu/Research/AI_Setter/kilter_climbs_data/oct2025-app-climbs.db`
Target subset: Kilter Board Original, 12 x 12 with kickboard, product_size_id=10, layout_id=1
Exported climb-angle rows: 261385

## Tables And Populated Fields
### ascents (0 rows)
- `uuid` TEXT: populated 0/0
- `climb_uuid` TEXT: populated 0/0
- `angle` INT UNSIGNED: populated 0/0
- `is_mirror` BOOLEAN: populated 0/0
- `user_id` INT UNSIGNED: populated 0/0
- `attempt_id` INT UNSIGNED: populated 0/0
- `bid_count` INT UNSIGNED: populated 0/0
- `quality` INT UNSIGNED: populated 0/0
- `difficulty` INT UNSIGNED: populated 0/0
- `is_benchmark` INT UNSIGNED: populated 0/0
- `comment` TEXT: populated 0/0
- `climbed_at` TEXT: populated 0/0
- `created_at` TEXT: populated 0/0
### attempts (38 rows)
- `id` INT UNSIGNED: populated 38/38
- `position` INT UNSIGNED: populated 38/38
- `name` TEXT: populated 38/38
### beta_links (31379 rows)
- `climb_uuid` TEXT: populated 31379/31379
- `link` TEXT: populated 31379/31379
- `foreign_username` TEXT: populated 24799/31379
- `angle` INT: populated 16281/31379
- `thumbnail` TEXT: populated 30380/31379
- `is_listed` BOOLEAN: populated 31379/31379
- `created_at` TEXT: populated 31379/31379
### bids (0 rows)
- `uuid` TEXT: populated 0/0
- `user_id` INT UNSIGNED: populated 0/0
- `climb_uuid` TEXT: populated 0/0
- `angle` INT UNSIGNED: populated 0/0
- `is_mirror` BOOLEAN: populated 0/0
- `bid_count` INT UNSIGNED: populated 0/0
- `comment` TEXT: populated 0/0
- `climbed_at` TEXT: populated 0/0
- `created_at` TEXT: populated 0/0
### circuits (0 rows)
- `uuid` TEXT: populated 0/0
- `name` TEXT: populated 0/0
- `description` TEXT: populated 0/0
- `color` TEXT: populated 0/0
- `user_id` INT UNSIGNED: populated 0/0
- `is_public` BOOLEAN: populated 0/0
- `created_at` TEXT: populated 0/0
- `updated_at` TEXT: populated 0/0
### circuits_climbs (0 rows)
- `circuit_uuid` TEXT: populated 0/0
- `climb_uuid` TEXT: populated 0/0
- `position` INT UNSIGNED: populated 0/0
### climb_cache_fields (192886 rows)
- `climb_uuid` TEXT: populated 192886/192886
- `ascensionist_count` INT UNSIGNED: populated 192377/192886
- `display_difficulty` FLOAT UNSIGNED: populated 192377/192886
- `quality_average` FLOAT UNSIGNED: populated 192377/192886
### climb_random_positions (0 rows)
- `climb_uuid` TEXT: populated 0/0
- `position` INT UNSIGNED: populated 0/0
### climb_stats (323416 rows)
- `climb_uuid` TEXT: populated 323416/323416
- `angle` INT UNSIGNED: populated 323416/323416
- `display_difficulty` FLOAT UNSIGNED: populated 323416/323416
- `benchmark_difficulty` FLOAT UNSIGNED: populated 634/323416
- `ascensionist_count` INT UNSIGNED: populated 323416/323416
- `difficulty_average` FLOAT UNSIGNED: populated 323416/323416
- `quality_average` FLOAT UNSIGNED: populated 323416/323416
- `fa_username` TEXT: populated 323416/323416
- `fa_at` TEXT: populated 323416/323416
### climbs (318097 rows)
- `uuid` TEXT: populated 318097/318097
- `layout_id` INT UNSIGNED: populated 318097/318097
- `setter_id` INT UNSIGNED: populated 318097/318097
- `setter_username` TEXT: populated 318097/318097
- `name` TEXT: populated 318097/318097
- `description` TEXT: populated 318097/318097
- `hsm` INT UNSIGNED: populated 318097/318097
- `edge_left` INT UNSIGNED: populated 318097/318097
- `edge_right` INT UNSIGNED: populated 318097/318097
- `edge_bottom` INT UNSIGNED: populated 318097/318097
- `edge_top` INT UNSIGNED: populated 318097/318097
- `angle` INT: populated 214523/318097
- `frames_count` INT UNSIGNED: populated 318097/318097
- `frames_pace` INT UNSIGNED: populated 318097/318097
- `frames` TEXT: populated 318097/318097
- `is_draft` BOOLEAN: populated 318097/318097
- `is_listed` BOOLEAN: populated 318097/318097
- `created_at` TEXT: populated 318097/318097
- `is_nomatch` BOOLEAN: populated 318097/318097
### difficulty_grades (39 rows)
- `difficulty` INT UNSIGNED: populated 39/39
- `boulder_name` TEXT: populated 39/39
- `route_name` TEXT: populated 39/39
- `is_listed` BOOLEAN: populated 39/39
### holes (3294 rows)
- `id` INT UNSIGNED: populated 3294/3294
- `product_id` INT UNSIGNED: populated 3294/3294
- `name` TEXT: populated 3294/3294
- `x` INT: populated 3294/3294
- `y` INT: populated 3294/3294
- `mirrored_hole_id` INT UNSIGNED: populated 3294/3294
- `mirror_group` INT UNSIGNED: populated 3294/3294
### kits (97 rows)
- `serial_number` TEXT: populated 97/97
- `name` TEXT: populated 97/97
- `is_autoconnect` BOOLEAN: populated 97/97
- `is_listed` BOOLEAN: populated 97/97
- `created_at` TEXT: populated 97/97
- `updated_at` TEXT: populated 97/97
### layouts (8 rows)
- `id` INT UNSIGNED: populated 8/8
- `product_id` INT UNSIGNED: populated 8/8
- `name` TEXT: populated 8/8
- `instagram_caption` TEXT: populated 8/8
- `is_mirrored` BOOLEAN: populated 8/8
- `is_listed` BOOLEAN: populated 8/8
- `password` TEXT: populated 6/8
- `created_at` TEXT: populated 8/8
### leds (7828 rows)
- `id` INT UNSIGNED: populated 7828/7828
- `product_size_id` INT UNSIGNED: populated 7828/7828
- `hole_id` INT UNSIGNED: populated 7828/7828
- `position` INT UNSIGNED: populated 7828/7828
### placement_roles (30 rows)
- `id` INT UNSIGNED: populated 30/30
- `product_id` INT UNSIGNED: populated 30/30
- `position` INT UNSIGNED: populated 30/30
- `name` TEXT: populated 30/30
- `full_name` TEXT: populated 30/30
- `led_color` TEXT: populated 30/30
- `screen_color` TEXT: populated 30/30
### placements (3773 rows)
- `id` INT UNSIGNED: populated 3773/3773
- `layout_id` INT UNSIGNED: populated 3773/3773
- `hole_id` INT UNSIGNED: populated 3773/3773
- `set_id` INT UNSIGNED: populated 3773/3773
- `default_placement_role_id` INT UNSIGNED: populated 2621/3773
### product_sizes (22 rows)
- `id` INT UNSIGNED: populated 22/22
- `product_id` INT UNSIGNED: populated 22/22
- `edge_left` INT: populated 22/22
- `edge_right` INT: populated 22/22
- `edge_bottom` INT: populated 22/22
- `edge_top` INT: populated 22/22
- `name` TEXT: populated 22/22
- `description` TEXT: populated 22/22
- `image_filename` TEXT: populated 22/22
- `position` INT UNSIGNED: populated 22/22
- `is_listed` BOOLEAN: populated 22/22
### product_sizes_layouts_sets (41 rows)
- `id` INT UNSIGNED: populated 41/41
- `product_size_id` INT UNSIGNED: populated 41/41
- `layout_id` INT UNSIGNED: populated 41/41
- `set_id` INT UNSIGNED: populated 41/41
- `image_filename` TEXT: populated 41/41
- `is_listed` BOOLEAN: populated 41/41
### products (7 rows)
- `id` INT UNSIGNED: populated 7/7
- `name` TEXT: populated 7/7
- `is_listed` BOOLEAN: populated 7/7
- `password` TEXT: populated 0/7
- `min_count_in_frame` INT UNSIGNED: populated 7/7
- `max_count_in_frame` INT UNSIGNED: populated 7/7
### products_angles (56 rows)
- `product_id` INT UNSIGNED: populated 56/56
- `angle` INT: populated 56/56
### sets (11 rows)
- `id` INT UNSIGNED: populated 11/11
- `name` TEXT: populated 11/11
- `hsm` INT UNSIGNED: populated 11/11
### shared_syncs (17 rows)
- `table_name` TEXT: populated 17/17
- `last_synchronized_at` TEXT: populated 17/17
### sqlite_stat1 (23 rows)
- `tbl` : populated 23/23
- `idx` : populated 23/23
- `stat` : populated 23/23
### tags (0 rows)
- `entity_uuid` TEXT: populated 0/0
- `user_id` INT UNSIGNED: populated 0/0
- `name` TEXT: populated 0/0
- `is_listed` BOOLEAN: populated 0/0
### user_permissions (0 rows)
- `user_id` INT UNSIGNED: populated 0/0
- `name` TEXT: populated 0/0
### user_syncs (0 rows)
- `user_id` INT UNSIGNED: populated 0/0
- `table_name` TEXT: populated 0/0
- `last_synchronized_at` TEXT: populated 0/0
### users (0 rows)
- `id` INT UNSIGNED: populated 0/0
- `username` TEXT: populated 0/0
- `created_at` TEXT: populated 0/0
### walls (0 rows)
- `uuid` TEXT: populated 0/0
- `user_id` INT UNSIGNED: populated 0/0
- `name` TEXT: populated 0/0
- `product_id` INT UNSIGNED: populated 0/0
- `is_adjustable` BOOLEAN: populated 0/0
- `angle` INT UNSIGNED: populated 0/0
- `layout_id` INT UNSIGNED: populated 0/0
- `product_size_id` INT UNSIGNED: populated 0/0
- `hsm` INT UNSIGNED: populated 0/0
- `serial_number` TEXT: populated 0/0
- `created_at` TEXT: populated 0/0
### walls_sets (0 rows)
- `wall_uuid` TEXT: populated 0/0
- `set_id` INT UNSIGNED: populated 0/0

## Grade Distribution By Angle
- 0 degrees: 3092 rows; {'4a/V0': 457, '4b/V0': 296, '4c/V0': 247, '5a/V1': 322, '5b/V1': 294, '5c/V2': 333, '6a/V3': 329, '6a+/V3': 235, '6b/V4': 245, '6b+/V4': 110, '6c/V5': 103, '6c+/V5': 83, '7a/V6': 23, '7a+/V7': 9, '7b/V8': 1, '7b+/V8': 1, '7c/V9': 3, '7c+/V10': 1}
- 5 degrees: 2259 rows; {'4a/V0': 196, '4b/V0': 214, '4c/V0': 226, '5a/V1': 206, '5b/V1': 234, '5c/V2': 312, '6a/V3': 280, '6a+/V3': 177, '6b/V4': 188, '6b+/V4': 76, '6c/V5': 82, '6c+/V5': 37, '7a/V6': 22, '7a+/V7': 6, '7b/V8': 1, '7b+/V8': 1, '8a/V11': 1}
- 10 degrees: 5614 rows; {'4a/V0': 491, '4b/V0': 437, '4c/V0': 470, '5a/V1': 442, '5b/V1': 571, '5c/V2': 720, '6a/V3': 755, '6a+/V3': 444, '6b/V4': 508, '6b+/V4': 267, '6c/V5': 250, '6c+/V5': 97, '7a/V6': 101, '7a+/V7': 33, '7b/V8': 11, '7b+/V8': 10, '7c/V9': 3, '7c+/V10': 2, '8a/V11': 2}
- 15 degrees: 8756 rows; {'4a/V0': 428, '4b/V0': 412, '4c/V0': 438, '5a/V1': 634, '5b/V1': 777, '5c/V2': 1142, '6a/V3': 1257, '6a+/V3': 846, '6b/V4': 880, '6b+/V4': 602, '6c/V5': 538, '6c+/V5': 302, '7a/V6': 294, '7a+/V7': 154, '7b/V8': 37, '7b+/V8': 9, '7c/V9': 1, '7c+/V10': 2, '8a/V11': 1, '8a+/V12': 1, '8c/V15': 1}
- 20 degrees: 16220 rows; {'4a/V0': 582, '4b/V0': 602, '4c/V0': 692, '5a/V1': 952, '5b/V1': 1250, '5c/V2': 1999, '6a/V3': 2292, '6a+/V3': 1576, '6b/V4': 1812, '6b+/V4': 1144, '6c/V5': 1232, '6c+/V5': 761, '7a/V6': 761, '7a+/V7': 365, '7b/V8': 140, '7b+/V8': 34, '7c/V9': 18, '7c+/V10': 7, '8a/V11': 1}
- 25 degrees: 13305 rows; {'4a/V0': 336, '4b/V0': 418, '4c/V0': 465, '5a/V1': 609, '5b/V1': 866, '5c/V2': 1504, '6a/V3': 1798, '6a+/V3': 1367, '6b/V4': 1607, '6b+/V4': 1115, '6c/V5': 1213, '6c+/V5': 669, '7a/V6': 764, '7a+/V7': 366, '7b/V8': 148, '7b+/V8': 45, '7c/V9': 10, '7c+/V10': 4, '8b+/V14': 1}
- 30 degrees: 37220 rows; {'4a/V0': 587, '4b/V0': 608, '4c/V0': 700, '5a/V1': 1045, '5b/V1': 1565, '5c/V2': 2756, '6a/V3': 4234, '6a+/V3': 3425, '6b/V4': 5019, '6b+/V4': 3563, '6c/V5': 4446, '6c+/V5': 2697, '7a/V6': 3262, '7a+/V7': 1716, '7b/V8': 908, '7b+/V8': 393, '7c/V9': 206, '7c+/V10': 64, '8a/V11': 16, '8a+/V12': 3, '8b/V13': 3, '8b+/V14': 3, '8c/V15': 1}
- 35 degrees: 17575 rows; {'4a/V0': 206, '4b/V0': 261, '4c/V0': 278, '5a/V1': 422, '5b/V1': 666, '5c/V2': 1054, '6a/V3': 1606, '6a+/V3': 1360, '6b/V4': 1987, '6b+/V4': 1664, '6c/V5': 2105, '6c+/V5': 1476, '7a/V6': 1995, '7a+/V7': 1233, '7b/V8': 663, '7b+/V8': 311, '7c/V9': 195, '7c+/V10': 79, '8a/V11': 13, '8a+/V12': 1}
- 40 degrees: 77008 rows; {'4a/V0': 570, '4b/V0': 707, '4c/V0': 632, '5a/V1': 948, '5b/V1': 1470, '5c/V2': 2270, '6a/V3': 4110, '6a+/V3': 3747, '6b/V4': 6551, '6b+/V4': 5765, '6c/V5': 9224, '6c+/V5': 6962, '7a/V6': 12077, '7a+/V7': 9285, '7b/V8': 6082, '7b+/V8': 3208, '7c/V9': 2272, '7c+/V10': 821, '8a/V11': 242, '8a+/V12': 58, '8b/V13': 7}
- 45 degrees: 37466 rows; {'4a/V0': 168, '4b/V0': 284, '4c/V0': 274, '5a/V1': 389, '5b/V1': 564, '5c/V2': 932, '6a/V3': 1583, '6a+/V3': 1541, '6b/V4': 2579, '6b+/V4': 2306, '6c/V5': 3659, '6c+/V5': 3178, '7a/V6': 5953, '7a+/V7': 5069, '7b/V8': 3615, '7b+/V8': 2083, '7c/V9': 1892, '7c+/V10': 955, '8a/V11': 357, '8a+/V12': 69, '8b/V13': 16}
- 50 degrees: 28773 rows; {'4a/V0': 136, '4b/V0': 217, '4c/V0': 172, '5a/V1': 280, '5b/V1': 380, '5c/V2': 575, '6a/V3': 1023, '6a+/V3': 896, '6b/V4': 1536, '6b+/V4': 1373, '6c/V5': 2224, '6c+/V5': 1929, '7a/V6': 3612, '7a+/V7': 3528, '7b/V8': 3210, '7b+/V8': 2267, '7c/V9': 2523, '7c+/V10': 1560, '8a/V11': 870, '8a+/V12': 368, '8b/V13': 90, '8b+/V14': 2, '8c/V15': 2}
- 55 degrees: 5613 rows; {'4a/V0': 19, '4b/V0': 53, '4c/V0': 66, '5a/V1': 69, '5b/V1': 104, '5c/V2': 136, '6a/V3': 220, '6a+/V3': 199, '6b/V4': 309, '6b+/V4': 273, '6c/V5': 377, '6c+/V5': 301, '7a/V6': 613, '7a+/V7': 483, '7b/V8': 456, '7b+/V8': 436, '7c/V9': 545, '7c+/V10': 384, '8a/V11': 410, '8a+/V12': 138, '8b/V13': 19, '8b+/V14': 3}
- 60 degrees: 5818 rows; {'4a/V0': 5, '4b/V0': 57, '4c/V0': 60, '5a/V1': 80, '5b/V1': 150, '5c/V2': 131, '6a/V3': 235, '6a+/V3': 224, '6b/V4': 304, '6b+/V4': 260, '6c/V5': 414, '6c+/V5': 367, '7a/V6': 666, '7a+/V7': 592, '7b/V8': 473, '7b+/V8': 384, '7c/V9': 575, '7c+/V10': 486, '8a/V11': 259, '8a+/V12': 64, '8b/V13': 26, '8b+/V14': 2, '8c/V15': 4}
- 65 degrees: 810 rows; {'4a/V0': 9, '4b/V0': 7, '4c/V0': 16, '5a/V1': 23, '5b/V1': 34, '5c/V2': 30, '6a/V3': 32, '6a+/V3': 38, '6b/V4': 61, '6b+/V4': 45, '6c/V5': 62, '6c+/V5': 52, '7a/V6': 91, '7a+/V7': 98, '7b/V8': 63, '7b+/V8': 33, '7c/V9': 45, '7c+/V10': 25, '8a/V11': 32, '8a+/V12': 10, '8b+/V14': 4}
- 70 degrees: 1856 rows; {'4a/V0': 51, '4b/V0': 22, '4c/V0': 24, '5a/V1': 53, '5b/V1': 62, '5c/V2': 77, '6a/V3': 98, '6a+/V3': 89, '6b/V4': 103, '6b+/V4': 89, '6c/V5': 112, '6c+/V5': 135, '7a/V6': 217, '7a+/V7': 169, '7b/V8': 168, '7b+/V8': 113, '7c/V9': 121, '7c+/V10': 79, '8a/V11': 48, '8a+/V12': 19, '8b/V13': 3, '8b+/V14': 3, '8c/V15': 1}
