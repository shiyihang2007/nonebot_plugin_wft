# nonebot_plugin_wft (Werewolf) - Agent Notes

This is a local NoneBot2 plugin living under `src/plugins/nonebot_plugin_wft/` (git submodule).

## What This Plugin Does
- Protocol: OneBot v11 adapter (group + private messages).
- Game: room-per-group Werewolf ("狼人杀") with an event-driven role system.
- Current implemented roles: Wolf / Seer / Guard / Witch / Villager.
- Phase loop: `lobby -> night -> day(speech) -> vote -> night ... -> ended`
  - Day speech runs before voting.
  - Speech order flips every day (day 1 ascending seats, day 2 descending, etc.).
- Private-message support for night skills; if a user is in multiple active rooms, PM commands can specify a target group id:
  - `wft.skill -g <group_id> <action> [args]` or `wft.skill <group_id> <action> [args]`
  - `wft.skip -g <group_id>` or `wft.skip <group_id>`

## Key Files / Layout
- User-facing docs: `src/plugins/nonebot_plugin_wft/README.md`
- `src/plugins/nonebot_plugin_wft/__init__.py`
  - NoneBot command wiring, admin gating (`wftconfig`), and the per-group `rooms` registry.
  - Private-message room resolution + optional `-g/--group` parsing for ambiguous users.
  - Special behavior: if a room is already `ended`, a new `wft.init` creates a fresh room but keeps the previous player list + role config (quick rematch).
- `src/plugins/nonebot_plugin_wft/game/room.py`
  - Core state machine and game rules (night resolution, day speech, vote, winner checks).
  - Role loading: dynamically imports `game/character_*.py` modules and collects `CharacterBase` subclasses.
- `src/plugins/nonebot_plugin_wft/game/event_system.py`, `src/plugins/nonebot_plugin_wft/game/event_base.py`
  - Minimal sequential event dispatcher (ordered `await` over listeners).
- `src/plugins/nonebot_plugin_wft/game/character_base.py`
  - Role base class; registers default listeners:
    - `event_night_start`, `event_day_start`, `event_vote_start`, `event_use_skill`, `event_person_killed`
- `src/plugins/nonebot_plugin_wft/game/character_*.py`
  - Role implementations. New roles should live here and use the `character_` filename prefix to be auto-loaded.

## Role Loading Rules (Important When Adding Roles)
- Modules are discovered by scanning `nonebot_plugin_wft.game` for files whose module name starts with `character_`.
- A role class is recognized if:
  - it is defined in that module, and
  - it subclasses `CharacterBase` (excluding `CharacterBase` itself).
- `/wft addrole ...` matches roles via `CharacterBase.aliases` tokens.

## Data Type Notes (OneBot)
- `Room.group_id` is stored as `int` (OneBot API expects numeric ids).
- `Player.user_id` is stored as `str` for dict keys; convert to `int` only when calling OneBot APIs.
