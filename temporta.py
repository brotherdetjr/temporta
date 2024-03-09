from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from typing import Dict

# TODO remove
logging.basicConfig(level=logging.DEBUG)


@dataclass
class UniverseDatabase:
    connection: Connection
    parent_universe_id: int | None


class Multiverse:
    instance_id: str
    mdb: Connection
    universe_dbs: Dict[int, UniverseDatabase]
    tick: int

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id
        self.universe_dbs = {}
        self.tick = 0

    def __enter__(self) -> Multiverse:
        database_path = f'{self.instance_id}/multiverse.db'
        database_exists = os.path.isfile(database_path)
        Path(self.instance_id).mkdir(parents=True, exist_ok=True)
        self.mdb = sqlite3.connect(database_path)
        self.mdb.execute('pragma foreign_keys = 1')
        if not database_exists:
            self.mdb.executescript('''
                create table players (
                    id text primary key
                );
                create table properties (
                    name text primary key,
                    value blob
                );
                create table universes (
                    id integer primary key,
                    parent_id integer,
                    
                    foreign key (parent_id) references universes (id)
                );
                create table characters (
                    id integer primary key,
                    parent_id integer,
                    universe_id integer,
                    player_id text,

                    foreign key (parent_id) references characters (id),
                    foreign key (universe_id) references universes (id),
                    foreign key (player_id) references players (id)
                );
                create table actions (
                    tick integer not null,
                    subtick integer not null,
                    payload text not null,
                    character_id integer not null,
                    universe_id integer,
                    
                    primary key (tick, subtick, payload, character_id),
                    foreign key (character_id) references characters (id),
                    foreign key (universe_id) references universes (id)
                );
            ''')
            self.mdb.execute(
                'insert into properties (name, value) values (?, ?)',
                ('tick', 0)
            )
            self.mdb.commit()
        for row in self.mdb.execute('select id, parent_id from universes').fetchall():
            self.universe_db_connect(row[0], row[1])
        return self

    def __exit__(self, *args) -> None:
        for _, udb in self.universe_dbs.items():
            udb.connection.close()
        self.mdb.close()

    def universe_db_connect(self, universe_id: int, parent_universe_id: int | None) -> None:
        conn: Connection = sqlite3.connect(f'{self.instance_id}/{universe_id}.db')
        conn.execute('pragma foreign_keys = 1')
        self.universe_dbs[universe_id] = UniverseDatabase(conn, parent_universe_id)

    def apply(
            self,
            payload: dict[str, str | int] | str | None = None,
            character_id: str | None = None  # TODO character_id-based authorisation?
    ) -> None:
        logging.debug({
            'event_type': 'BEFORE_APPLY',
            'tick': self.tick,
            'payload': payload
        })
        try:
            match (payload, character_id):

                case (
                    {
                        'kind': 'CreatePlayer',
                        'player_id': str() as player_id
                    },
                    None
                ):
                    self.mdb.execute('insert into players (id) values (?)', (player_id,))

                case (
                    {
                        'kind': 'CreateUniverse',
                        'parent_id': (int() | None) as parent_id
                    },
                    None,
                ):
                    universe_id: int = self.mdb.execute(
                        'insert into universes (parent_id) values (?)',
                        (parent_id,)
                    ).lastrowid
                    self.universe_db_connect(universe_id, parent_id)
                    udb: Connection = self.universe_dbs[universe_id].connection
                    udb.executescript('''
                        create table locations (
                            name text primary key,
                            description text not null
                        );
                        create table directions (
                            from_name text not null,
                            to_name text not null,
                            travel_time integer not null,
                            ordinal integer not null,

                            foreign key (from_name) references locations (name),
                            foreign key (to_name) references locations (name),
                            primary key (from_name, to_name),
                            unique (from_name, ordinal)
                        );
                        create index directions_from_name_idx on directions (from_name);
                    ''')

                case (
                    {
                        'kind': 'CreateLocation',
                        'universe_id': int() as universe_id,
                        'name': str() as name,
                        'description': (str() | None) as description
                    },
                    _
                ):
                    self.udb(universe_id).execute(
                        'insert into locations (name, description) values (?, ?)',
                        (name, description)
                    )

                case(
                    {
                        'kind': 'ConnectLocations',
                        'universe_id': int() as universe_id,
                        'from_name': str() as from_name,
                        'to_name': str() as to_name,
                        'travel_time': int() as travel_time
                    },
                    _
                ):
                    if from_name == to_name:
                        raise Exception('Cannot connect location to itself')
                    if travel_time < 0:
                        raise Exception('Travel time cannot be less than zero')
                    self.udb(universe_id).executemany(
                        '''
                            insert into directions values
                            (?, ?, ?, (select count(*) from directions where from_name = ?))
                        ''',
                        [
                            (from_name, to_name, travel_time, from_name),
                            (to_name, from_name, travel_time, to_name)
                        ]
                    )

                case(
                    {
                        'kind': 'CreateCharacter',
                        'parent_id': (int() | None) as parent_id,
                        'universe_id': (int() | None) as universe_id,
                        'player_id': (str() | None) as player_id
                    },
                    _
                ):
                    if parent_id is None and player_id is None:
                        raise Exception('parent_id or player_id must not be None')
                    self.mdb.execute(
                        'insert into characters (parent_id, universe_id, player_id) values (?, ?, ?)',
                        (parent_id, universe_id, player_id)
                    )

                # TODO handle unmatched

        except Exception as e:
            # TODO send error message back to user
            # TODO implement messaging

            logging.error({
                'event_type': 'APPLY_ERROR',
                'tick': self.tick,
                'value': {'error': e, 'payload': payload}
            })

    def udb(self, universe_id: int) -> Connection:
        return self.universe_dbs[universe_id].connection

    def record_action(
            self,
            subtick: int,
            payload: dict[str, str | int] | str | None = None,
    ) -> None:
        logging.debug({
            'event_type': 'STORE_ACTION',
            'tick': self.tick,
            'subtick': subtick,
            'payload': payload
        })
        self.mdb.execute(
            '''
                insert into actions (tick, subtick, payload, character_id, universe_id) 
                values (?, ?, ?, ?, ?)
            ''',
            (self.tick, subtick, json.dumps(payload), payload['character_id'], payload.get('universe_id'))
        )

    def commit(self) -> None:
        next_tick: int = self.mdb.execute('''
            update properties set value = value + 1 where name = 'tick' returning value
        ''').fetchone()[0]
        self.mdb.commit()
        for _, udb in self.universe_dbs.items():
            udb.connection.commit()
        self.tick = next_tick
