from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import unittest
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Connection
from typing import Dict, Any
from uuid import uuid4

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


class TestMultiverse(unittest.TestCase):
    multiverse: Multiverse
    mdb: Connection  # independent sqlite3 connection for tests

    def setUp(self):
        self.multiverse = Multiverse('.test-' + str(uuid4()))
        self.multiverse.__enter__()
        self.mdb = sqlite3.connect(f'{self.multiverse.instance_id}/multiverse.db')

    def tearDown(self):
        self.multiverse.__exit__()
        self.mdb.close()
        shutil.rmtree(self.multiverse.instance_id)

    def test_create_multiverse(self):
        # expect
        self.assertEqual(
            [('tick', 0)],
            self.mdb.execute('select name, value from properties').fetchall()
        )

    def test_create_player(self):
        # when
        self.multiverse.apply({'kind': 'CreatePlayer', 'player_id': 'player1'})
        self.multiverse.apply({'kind': 'CreatePlayer', 'player_id': 'player2'})
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('player1',), ('player2',)],
            self.mdb.execute('select id from players').fetchall()
        )
        # when duplicate is requested
        self.multiverse.apply({'kind': 'CreatePlayer', 'player_id': 'player2'})
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('player1',), ('player2',)],
            self.mdb.execute('select id from players').fetchall()
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply({'kind': 'CreateUniverse', 'parent_id': None})
        self.multiverse.commit()
        # then first universe db is created
        with self.udb(1) as udb:
            self.assertEqual(
                ('empty',),
                udb.execute("select 'empty'").fetchone()
            )
        # and 100500th db is not created yet
        with self.assertRaises(Exception):
            self.udb(100500)

    def test_create_location(self):
        # given
        self.multiverse.apply({'kind': 'CreateUniverse', 'parent_id': None})
        # when
        self.multiverse.apply({
            'kind': 'CreateLocation',
            'universe_id': 1,
            'name': 'Strezhevoy',
            'description': 'The best town in the world'
        })
        self.multiverse.commit()
        # then
        with self.udb(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )
        # when a location with duplicate name is added
        self.multiverse.apply({
            'kind': 'CreateLocation',
            'universe_id': 1,
            'name': 'Strezhevoy',
            'description': 'The best town in the world'
        })
        self.multiverse.commit()
        # then nothing is changed
        with self.udb(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )

    def test_connect_locations(self):
        # given
        self.multiverse.apply({'kind': 'CreateUniverse', 'parent_id': None})
        self.multiverse.apply({
            'kind': 'CreateLocation',
            'universe_id': 1,
            'name': 'Strezhevoy',
            'description': 'The best town in the world'
        })
        self.multiverse.apply({
            'kind': 'CreateLocation',
            'universe_id': 1,
            'name': 'Beijing',
            'description': 'The capital of China'
        })
        self.multiverse.apply({
            'kind': 'CreateLocation',
            'universe_id': 1,
            'name': 'London',
            'description': 'The capital of the UK'
        })
        # when
        self.multiverse.apply(
            {
                'kind': 'ConnectLocations',
                'universe_id': 1,
                'from_name': 'Strezhevoy',
                'to_name': 'Beijing',
                'travel_time': 3510
            }
        )
        self.multiverse.apply(
            {
                'kind': 'ConnectLocations',
                'universe_id': 1,
                'from_name': 'Strezhevoy',
                'to_name': 'London',
                'travel_time': 6000
            }
        )
        self.multiverse.commit()
        # then
        with self.udb(1) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                udb.execute('select from_name, to_name, travel_time, ordinal from directions').fetchall()
            )
        # when inserting duplicate
        self.multiverse.apply(
            {
                'kind': 'ConnectLocations',
                'universe_id': 1,
                'from_name': 'Strezhevoy',
                'to_name': 'Beijing',
                'travel_time': 9000
            }
        )
        self.multiverse.commit()
        # then nothing changes
        with self.udb(1) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                udb.execute('select from_name, to_name, travel_time, ordinal from directions').fetchall()
            )
        # when linking to itself
        self.multiverse.apply(
            {
                'kind': 'ConnectLocations',
                'universe_id': 1,
                'from_name': 'Strezhevoy',
                'to_name': 'Strezhevoy',
                'travel_time': 100500
            }
        )
        self.multiverse.commit()
        # then nothing changes
        with self.udb(1) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                udb.execute('select from_name, to_name, travel_time, ordinal from directions').fetchall()
            )
        # when linking with negative travel time
        self.multiverse.apply(
            {
                'kind': 'ConnectLocations',
                'universe_id': 1,
                'from_name': 'London',
                'to_name': 'Beijing',
                'travel_time': -2
            }
        )
        self.multiverse.commit()
        # then nothing changes
        with self.udb(1) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                udb.execute('select from_name, to_name, travel_time, ordinal from directions').fetchall()
            )

    def test_commit(self):
        # expect
        self.assertEqual(
            0,
            self.mdb.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(
            1,
            self.mdb.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(
            2,
            self.mdb.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )

    # TODO test for CreateCharacter
    def test_record_action(self):
        # given
        self.multiverse.apply({'kind': 'CreateUniverse', 'parent_id': None})
        self.multiverse.apply({'kind': 'CreatePlayer', 'player_id': 'player1'})
        self.multiverse.apply({'kind': 'CreatePlayer', 'player_id': 'player2'})
        self.multiverse.apply({'kind': 'CreateCharacter', 'parent_id': None, 'universe_id': 1, 'player_id': 'player1'})
        self.multiverse.apply({'kind': 'CreateCharacter', 'parent_id': None, 'universe_id': 1, 'player_id': 'player2'})
        self.multiverse.commit()
        # when
        self.multiverse.record_action(
            42,
            {
                'kind': 'CreateLocation',
                'character_id': 1,
                'universe_id': 1,
                'name': 'Tbilisi',
                'description': 'The capital of Georgia'
            }
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': 1,
                    'payload': {
                        'kind': 'CreateLocation',
                        'character_id': 1,
                        'universe_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                }
            ],
            self.fetch_actions()
        )
        # when
        self.multiverse.record_action(
            9000,
            {
                'kind': 'CreateLocation',
                'character_id': 1,
                'universe_id': 1,
                'name': 'London',
                'description': 'The capital of the UK',
            }
        )
        self.multiverse.record_action(
            9001,
            {
                'kind': 'ConnectLocations',
                'character_id': 2,
                'from_name': 'London',
                'to_name': 'Tbilisi',
                'travel_time': 33,
            }
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': 1,
                    'payload': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'character_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9000,
                    'character_id': 1,
                    'payload': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'character_id': 1,
                        'name': 'London',
                        'description': 'The capital of the UK'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9001,
                    'character_id': 2,
                    'payload': {
                        'kind': 'ConnectLocations',
                        'character_id': 2,
                        'from_name': 'London',
                        'to_name': 'Tbilisi',
                        'travel_time': 33
                    }
                }
            ],
            self.fetch_actions()
        )

    def fetch_actions(self) -> list[Any]:
        with self.mdb as mdb:
            rows: list[Any] = mdb.execute(
                '''
                    select tick, subtick, character_id, payload
                    from actions order by tick, subtick
                '''
            ).fetchall()
            return list(map(lambda row: {
                'tick': row[0],
                'subtick': row[1],
                'character_id': row[2],
                'payload': json.loads(row[3])
            }, rows))

    # independent universe DB accessor
    def udb(self, universe_id: int) -> Connection:
        path = f'{self.multiverse.instance_id}/{universe_id}.db'
        # In the tests we really want to fail,
        # if the requested database does not exist.
        if not os.path.isfile(path):
            raise Exception(f'No such database: {path}')
        # noinspection PyTypeChecker
        return closing(sqlite3.connect(path))


if __name__ == '__main__':
    unittest.main()
