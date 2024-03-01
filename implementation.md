[temporta.py](temporta.py) WILL BE a draft implementation of the
[described idea](https://github.com/brotherdetjr/temporta/blob/master/README.md).
First version will:
- have a text-based UI (TUI)
- have the hardcoded [mission](https://github.com/brotherdetjr/temporta/blob/master/README.md#sample-mission)
- be single-player, but implementing the proposed
  [multiplayer architecture](https://github.com/brotherdetjr/temporta/blob/master/README.md#algorithms-and-entities),
  and having all extension points needed for conversion the prototype to a fully-fledged multiplayer server
- likely be a Web application
- persist game state on disk
- NOT have advanced performance optimisations
- NOT have internationalisation or localisation

Using Python as language providing a suitable balance between performance and code expressiveness.

Using SQLite as a single-file relational database.

Single file may be convenient for cloning universes' states -
we will try to reduce cloning operation to a file copying operation. It will be agnostic to the internal
database's structure.

Relational database appears suitable for modeling TUI-based game's world. In TUI world we are less likely to
need geometry/geography support. On the other hand, relational modeling is extremely flexible, powerful, and
familiar to most developers. Given that the game's world model is yet to be defined, this seems to be a good
choice.

`Multiverse` class embraces:
- A Multiverse database containing information shared among different Universes.
- A map of Universe databases containing Universe states.
- Logic of the state change both for Multiverse and all Universes, which is derived from incoming Actions.

## Multiverse Database Schema

Concrete schemas can be found in the [application](temporta.py) itself. In this section we will describe the
high-level relational model.

`players` table represents a Player's account.

A `character` may be controlled by a Player (one Player can control multiple Characters). If a Character is NOT linked
to any Player, this means it is controlled by a previously recorded Action Log of Character's twin in parent Universe.
Apparently, this is applicable only for the Universes where player time-travels to. The "root" Universe does not have
a parent.

Other columns in `character` table (`universe_id`, `location_name`) are used for efficient Character's localisation.
A Universe database may contain all necessary information about the Character, but we need to know in which Universe
the Character is based. Similar consideration can be applied for `location_name`.

TODO complete
