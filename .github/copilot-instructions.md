# NoneBot Plugin WFT - AI Coding Agent Instructions

## Project Overview
A **Werewolf Game (狼人杀) plugin** for NoneBot2 and OneBot11 protocol. The codebase is currently in refactoring.

## Architecture Overview

### Event-Driven Game Loop
The plugin uses an **event-based architecture** where game phases are triggered by events through the event system:

```
Room → EventSystem → Events (night_start, day_start, vote_start, person_killed, use_skill)
  ↓
  └→ Listeners → Character roles respond to events
```

**Key Files:**
- [game/events/event_system.py](../game/events/event_system.py) - Central event dispatcher per room
- [game/events/event_base.py](../game/events/event_base.py) - Event trigger mechanism with listener chain
- [game/events/listener.py](../game/events/listener.py) - Listener callback signature (room, user_id, args)

### Room-Based Isolation
Each game session is a separate `Room` instance:

```
Room {
  player_list: [Player, ...]      # Ordered by join sequence (order = number)
  id_2_player: {qq_id → Player}   # Quick lookup by QQ ID
  events_system: EventSystem       # Independent event processing
  character_enabled: {Role → count}  # Enabled character types and counts
}
```

**Key Pattern:** Always access players via `player_list[index]` for game logic (preserves turn order), but use `id_2_player[qq_id]` for user lookups.

### Character-Role System
- **Dynamic Loading:** Character classes auto-loaded from `game/characters/` at initialization
- **Registration Pattern:** Characters register event listeners when instantiated during game start
- **Base Class:** [game/characters/character_base.py](../game/characters/character_base.py)

Example implementation path: Create new role classes in `game/characters/character_[role_name].py`, inherit from `CharacterBase`, register event listeners in `__init__`.

## Plugin Integration Points

### Bot Command Dispatch (`__init__.py`)
Commands map to game events:

```python
# Admin commands (requires group admin role)
/wftconfig enable <group_id>
/wftconfig disable <group_id>
/wftconfig ban <user_ids>
/wftconfig unban <user_ids>

# Game commands (enabled groups only, user blacklist checked)
/wft init          # Create room
/wft start         # Begin game
/wft join          # Add player
/wft exit          # Remove player
/wft action        # Execute action (drug, knife, investigate)
/wft skill         # Use skill (explosion, gun, duel)
```

**Flow:** Command handler → triggers event on room's event_system → listeners execute game logic

## Developer Workflow & Patterns

### Adding a New Character Role
1. Create [game/characters/character_[name].py](../game/characters/)
2. Inherit from `CharacterBase`
3. Register event listeners in `__init__` that call methods on the room/player objects
4. Add to `character_modules` in [game/room.py](../game/room.py#L9) (auto-loaded)

### Adding a New Game Phase Event
1. Add `self.event_[phase_name] = EventBase()` in [EventSystem.__init__](../game/events/event_system.py)
2. Call `room.events_system.event_[phase_name].active(room, user_id, args)` to trigger
3. Characters register listeners via `room.events_system.event_[phase_name].listeners.append(listener_func)`

### Player Order Invariant
- `player_list` is ordered by join sequence; `order` field = index
- When removing player: must decrement `order` for all players after removal
- See [Room.remove_player()](../game/room.py#L20-L24) for correct implementation

## Critical Conventions

- **Listener Signature:** `def listener(room: Room, user_id: str | None, args: list[str]) -> Any`
- **Event Activation:** Always pass `Room` object so listeners can modify game state
- **User ID Handling:** QQ IDs stored as strings; convert group IDs to str for dict keys
- **No Global Game State:** Each room is independent; store state in Room/Player/Character objects
- **Async Context:** Bot integration is async; game logic should be sync where possible

## Import Structure
- Relative imports within `game/` module (e.g., `from .characters.character_base import CharacterBase`)
- Absolute imports from NoneBot: `from nonebot.adapters.onebot.v11 import Bot, Message, ...`

## Testing & Debugging Tips
- Room instances stored in global `rooms` dict keyed by group_id
- Enable debug logging via NoneBot's logger (imported at module level)
- Event system calls all listeners sequentially; check listener registration order if behavior differs
