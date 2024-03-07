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
    multiverse_db: Connection
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
        self.multiverse_db = sqlite3.connect(database_path)
        self.multiverse_db.execute('pragma foreign_keys = 1')
        if not database_exists:
            self.multiverse_db.executescript('''
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
                    kind text not null,
                    payload text not null,
                    character_id integer not null,
                    universe_id integer,
                    
                    primary key (tick, subtick, kind, payload, character_id),
                    foreign key (character_id) references characters (id),
                    foreign key (universe_id) references universes (id)
                );
            ''')
            self.multiverse_db.execute(
                'insert into properties (name, value) values (?, ?)',
                ('tick', 0)
            )
            self.multiverse_db.commit()
        for row in self.multiverse_db.execute('select id, parent_id from universes').fetchall():
            self.__universe_db_connect(row[0], row[1])
        return self

    def __exit__(self, *args) -> None:
        for _, udb in self.universe_dbs.items():
            udb.connection.close()
        self.multiverse_db.close()

    def __universe_db_connect(self, universe_id: int, parent_universe_id: int | None) -> None:
        conn: Connection = sqlite3.connect(f'{self.instance_id}/{universe_id}.db')
        conn.execute('pragma foreign_keys = 1')
        self.universe_dbs[universe_id] = UniverseDatabase(conn, parent_universe_id)

    def apply(
            self,
            kind: str,
            payload: dict[str, str | int] | str | None = None,
            character_id: str | None = None
    ) -> None:
        logging.debug({
            'event_type': 'BEFORE_APPLY',
            'tick': self.tick,
            'value': {'kind': kind, 'payload': payload}
        })
        mdb = self.multiverse_db
        try:
            match (kind, payload, character_id):
                case ('CreatePlayer', str(player_id), None):
                    mdb.execute('insert into players (id) values (?)', (player_id,))
                case ('CreateUniverse', (int() | None) as parent_id, None):
                    uid: int = mdb.execute(
                        'insert into universes (parent_id) values (?)',
                        (parent_id,)
                    ).lastrowid
                    self.__universe_db_connect(uid, parent_id)
                    udb: Connection = self.universe_dbs[uid].connection
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
                case (_, dict({'universe_id': int(uid)}) as payload, _):
                    udb: UniverseDatabase = self.universe_dbs[uid]
                    match kind:
                        case 'CreateLocation':
                            udb.connection.execute(
                                'insert into locations (name, description) values (?, ?)',
                                (payload['name'], payload['description'])
                            )
                        case 'ConnectLocations':
                            from_name = payload['from_name']
                            to_name = payload['to_name']
                            travel_time = payload['travel_time']
                            if from_name == to_name:
                                raise Exception('Cannot connect location to itself')
                            if travel_time < 0:
                                raise Exception('Travel time cannot be less than zero')
                            udb.connection.executemany(
                                '''
                                    insert into directions values
                                    (?, ?, ?, (select count(*) from directions where from_name = ?))
                                ''',
                                [
                                    (from_name, to_name, travel_time, from_name),
                                    (to_name, from_name, travel_time, to_name)
                                ]
                            )
                        case 'CreateCharacter':
                            mdb.execute(
                                'insert into characters (parent_id, universe_id, player_id) values (?, ?, ?)',
                                (payload.get('parent_id'), payload.get('universe_id'), payload.get('player_id'))
                            )

        except Exception as e:
            # TODO send error message back to user
            # TODO implement messaging

            logging.error({
                'event_type': 'APPLY_ERROR',
                'tick': self.tick,
                'value': {'error': e, 'kind': kind, 'payload': payload}
            })

    def record_action(
            self,
            subtick: int,
            kind: str,
            payload: dict[str, str | int] | str | None = None,
    ) -> None:
        logging.debug({
            'event_type': 'STORE_ACTION',
            'tick': self.tick,
            'subtick': subtick,
            'value': {'kind': kind, 'payload': payload}
        })
        self.multiverse_db.execute(
            '''
                insert into actions (tick, subtick, kind, payload, character_id, universe_id) 
                values (?, ?, ?, ?, ?, ?)
            ''',
            (self.tick, subtick, kind, json.dumps(payload), payload['character_id'], payload.get('universe_id'))
        )

    def commit(self) -> None:
        next_tick: int = self.multiverse_db.execute('''
            update properties set value = value + 1 where name = 'tick' returning value
        ''').fetchone()[0]
        self.multiverse_db.commit()
        for _, udb in self.universe_dbs.items():
            udb.connection.commit()
        self.tick = next_tick


class TestMultiverse(unittest.TestCase):
    multiverse: Multiverse
    multiverse_db: Connection  # independent sqlite3 connection for tests

    def setUp(self):
        self.multiverse = Multiverse('.test-' + str(uuid4()))
        self.multiverse.__enter__()
        self.multiverse_db = sqlite3.connect(f'{self.multiverse.instance_id}/multiverse.db')

    def tearDown(self):
        self.multiverse.__exit__()
        self.multiverse_db.close()
        shutil.rmtree(self.multiverse.instance_id)

    def test_create_multiverse(self):
        # expect
        self.assertEqual(
            [('tick', 0)],
            self.multiverse_db.execute('select name, value from properties').fetchall()
        )

    def test_create_player(self):
        # when
        self.multiverse.apply('CreatePlayer', 'player1')
        self.multiverse.apply('CreatePlayer', 'player2')
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('player1',), ('player2',)],
            self.multiverse_db.execute('select id from players').fetchall()
        )
        # when duplicate is requested
        self.multiverse.apply('CreatePlayer', 'player2')
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('player1',), ('player2',)],
            self.multiverse_db.execute('select id from players').fetchall()
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply('CreateUniverse')
        self.multiverse.commit()
        # then first universe db is created
        with self.universe_db(1) as udb:
            self.assertEqual(
                ('empty',),
                udb.execute("select 'empty'").fetchone()
            )
        # and 100500th db is not created yet
        with self.assertRaises(Exception):
            self.universe_db(100500)

    def test_create_location(self):
        # given
        self.multiverse.apply('CreateUniverse')
        # when
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 1, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        self.multiverse.commit()
        # then
        with self.universe_db(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )
        # when a location with duplicate name is added
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 1, 'name': 'Strezhevoy', 'description': 'Some other description'}
        )
        self.multiverse.commit()
        # then nothing is changed
        with self.universe_db(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )

    def test_connect_locations(self):
        # given
        self.multiverse.apply('CreateUniverse')
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 1, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 1, 'name': 'Beijing', 'description': 'The capital of China'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 1, 'name': 'London', 'description': 'The capital of the UK'}
        )
        # when
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 1, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 3510}
        )
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 1, 'from_name': 'Strezhevoy', 'to_name': 'London', 'travel_time': 6000}
        )
        self.multiverse.commit()
        # then
        with self.universe_db(1) as udb:
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
            'ConnectLocations',
            {'universe_id': 1, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 9000}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.universe_db(1) as udb:
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
            'ConnectLocations',
            {'universe_id': 1, 'from_name': 'Strezhevoy', 'to_name': 'Strezhevoy', 'travel_time': 100500}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.universe_db(1) as udb:
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
            'ConnectLocations',
            {'universe_id': 1, 'from_name': 'London', 'to_name': 'Beijing', 'travel_time': -2}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.universe_db(1) as udb:
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
            self.multiverse_db.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(
            1,
            self.multiverse_db.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(
            2,
            self.multiverse_db.execute('''
                select value from properties where name='tick'
            ''').fetchone()[0]
        )

    # TODO test for CreateCharacter
    def test_record_action(self):
        # given
        self.multiverse.apply('CreateUniverse')
        self.multiverse.apply('CreatePlayer', 'player1')
        self.multiverse.apply('CreateCharacter', {'universe_id': 1, 'player_id': 'player1'})
        self.multiverse.apply('CreateCharacter', {'universe_id': 1})
        self.multiverse.commit()
        # when
        self.multiverse.record_action(
            42,
            'CreateLocation',
            {'universe_id': 1, 'character_id': 1, 'name': 'Tbilisi', 'description': 'The capital of Georgia'}
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'kind': 'CreateLocation',
                    'character_id': 1,
                    'payload': {
                        'universe_id': 1,
                        'character_id': 1,
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
            'CreateLocation',
            {'universe_id': 1, 'character_id': 1, 'name': 'London', 'description': 'The capital of the UK'}
        )
        self.multiverse.record_action(
            9001,
            'ConnectLocations',
            {'character_id': 2, 'from_name': 'London', 'to_name': 'Tbilisi', 'travel_time': 33}
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'kind': 'CreateLocation',
                    'character_id': 1,
                    'payload': {
                        'universe_id': 1,
                        'character_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9000,
                    'kind': 'CreateLocation',
                    'character_id': 1,
                    'payload': {
                        'universe_id': 1,
                        'character_id': 1,
                        'name': 'London',
                        'description': 'The capital of the UK'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9001,
                    'kind': 'ConnectLocations',
                    'character_id': 2,
                    'payload': {
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
        with self.multiverse_db as mdb:
            rows: list[Any] = mdb.execute(
                '''
                    select tick, subtick, kind, character_id, payload
                    from actions order by tick, subtick
                '''
            ).fetchall()
            return list(map(lambda row: {
                'tick': row[0],
                'subtick': row[1],
                'kind': row[2],
                'character_id': row[3],
                'payload': json.loads(row[4])
            }, rows))

    # independent universe DB accessor
    def universe_db(self, universe_id: int) -> Connection:
        path = f'{self.multiverse.instance_id}/{universe_id}.db'
        # In the tests we really want to fail,
        # if the requested database does not exist.
        if not os.path.isfile(path):
            raise Exception(f'No such database: {path}')
        # noinspection PyTypeChecker
        return closing(sqlite3.connect(path))


if __name__ == '__main__':
    unittest.main()
