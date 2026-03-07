# Known Issues (Test Layer)

以下为当前通过 `xfail` 标记的规范期望用例，均要求后续修复后移除：

1. `WFT-TEST-001`  
   - 文件：`tests/game/test_room_flow.py`  
   - 用例：`test_on_night_end__spec_should_dispatch_person_killed_for_each_pending_record`  
   - 退出条件：`room._on_night_end` 改为按 `pending_death_records.items()` 遍历并通过该用例。

2. `WFT-TEST-002`  
   - 文件：`tests/game/test_character_hunter.py`  
   - 用例：`test_on_skip__spec_empty_args_should_skip`  
   - 退出条件：`CharacterHunter.on_skip` 支持空参数直接放弃技能并解锁阻塞事件。

3. `WFT-TEST-003`  
   - 文件：`tests/game/test_character_black_wolf.py`  
   - 用例：`test_on_skip__spec_empty_args_should_skip`  
   - 退出条件：`CharacterBlackWolf.on_skip` 支持空参数直接放弃技能并解锁阻塞事件。

4. `WFT-TEST-004`  
   - 文件：`tests/game/test_character_witch.py`  
   - 用例：`test_on_skill__spec_save_without_target_should_not_consume_antidote`  
   - 退出条件：`CharacterWitch.on_skill(save)` 在无可救目标时不消耗解药。

说明：
- 当前 xfail 数量 = 4（小于上限 6）。
- 所有 xfail 均设置 `strict=False`，用于持续跟踪修复进度。
