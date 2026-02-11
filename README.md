# nonebot_plugin_wft

基于 nonebot2 和 onebot11 协议的狼人杀插件

此插件仍然处于重构状态

## TODO

- [X] 在夜晚行动造成角色死亡的，更改 room.pending_death_records
- [ ] 白天投票响应改为角色基类的监听器

## 使用

### 管理指令（需要群主/管理员，且需 @机器人）

- `@机器人 wftconfig.enable`：在当前群启用插件
- `@机器人 wftconfig.disable`：在当前群禁用插件
- `@机器人 wftconfig.ban <qq...>`：拉黑用户（不响应其游戏指令）
- `@机器人 wftconfig.unban <qq...>`：解除拉黑

### 房间与大厅

- `wft.init`：创建房间
  - 若上一局已结束（游戏状态为 `ended`），再次 `wft.init` 会创建新房间，并保留上一局的玩家列表与角色配置（方便快速再来一局）
- `@机器人 wft.end`：结束当前房间（清空本群房间）
- `wft.join`：加入游戏（仅大厅阶段可用）
- `wft.exit`：退出游戏（仅大厅阶段可用）
- `wft.addrole <角色...>`：添加角色配置（按别名；可一次添加多个）
- `wft.rmrole <角色...>`：删除角色配置
- `wft.autoroles`：自动配置角色（当前实现：按人数配置狼人 + 1 预言家，其余补足为村民）
- `wft.showroles`：显示当前已配置角色
- `wft.start`：开始游戏（分配身份并进入夜晚）

### 夜晚技能（可群聊或私聊）

所有夜晚技能统一通过 `wft.skill ...` 与 `wft.skip` 触发。
如果你同时在多个群的游戏中，私聊时需要指定群号：

- `wft.skill -g <群号> <动作> [参数]`
- `wft.skill <群号> <动作> [参数]`
- `wft.skip -g <群号>`
- `wft.skip <群号>`

当前已实现角色与用法：

- 狼人：`wft.skill kill <编号>`（或 `wft.skip` 放弃本夜击杀投票）
- 预言家：`wft.skill check <编号>`（或 `wft.skip` 放弃本夜查验）
- 守卫：`wft.skill guard <编号>`（或 `wft.skip` 放弃本夜守护；不可连续两晚守同一人）
- 女巫：
  - `wft.skill save` 使用解药（仅在狼刀锁定后可救人；解药一局一次）
  - `wft.skill poison <编号>` 使用毒药（毒药一局一次）
  - `wft.skip` 放弃本夜用药

### 白天发言与投票

- 夜晚结算后先进入白天发言阶段：按编号顺序依次发言
  - 每个白天发言顺序翻转一次：第 1 天从小到大，第 2 天从大到小，以此类推
  - 当前发言玩家发送 `wft.skip` 结束发言并轮到下一位
- 发言结束后自动进入投票：
  - `wft.vote <编号>` 投票放逐
  - `wft.skip` 弃票
