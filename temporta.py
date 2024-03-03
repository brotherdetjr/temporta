from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from sqlite3 import Connection
from typing import Dict
from uuid import uuid4

# TODO remove
logging.basicConfig(level=logging.DEBUG)


class Multiverse:
    instance_id: str
    __multiverse_db: Connection
    __universe_dbs: Dict[str, Connection] = {}
    __tick: int = 0
    __subtick: int = 0

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id

    def __enter__(self) -> Multiverse:
        database_path = f'{self.instance_id}/multiverse.db'
        database_exists = os.path.isfile(database_path)
        Path(self.instance_id).mkdir(parents=True, exist_ok=True)
        self.__multiverse_db = sqlite3.connect(database_path)
        self.__multiverse_db.execute('pragma foreign_keys = 1')
        if not database_exists:
            self.__multiverse_db.executescript('''
                create table players (
                    id text primary key
                );
                create table properties (
                    name text primary key,
                    value blob
                );
                create table universes (
                    id text primary key,
                    parent_id text,
                    
                    foreign key (parent_id) references universes (id)
                );
            ''')
            self.__multiverse_db.execute(
                'insert into properties (name, value) values (?, ?)',
                ['tick', 0]
            )
            self.__multiverse_db.commit()
        for row in self.__multiverse_db.execute('select id from universes').fetchall():
            self.__universe_db_connect(row[0])
        return self

    def __exit__(self, *args) -> None:
        for _, value in self.__universe_dbs.items():
            value.close()
        self.__multiverse_db.close()

    def __universe_db_connect(self, universe_id: str) -> None:
        conn: Connection = sqlite3.connect(f'{self.instance_id}/{universe_id}.db')
        conn.execute('pragma foreign_keys = 1')
        self.__universe_dbs[universe_id] = conn

    def apply(self, kind: str, payload: dict[str, str | int] | str | None = None) -> None:
        logging.debug({
            'event_type': 'BEFORE_APPLY',
            'tick': self.__tick,
            'subtick': self.__subtick,
            'value': {'kind': kind, 'payload': payload}
        })
        mdb = self.__multiverse_db
        try:
            match (kind, payload):
                case ('CreatePlayer', str(player_id)):
                    mdb.execute('insert into players (id) values (?)', [player_id])
                case ('CreateUniverse', (str() | None) as parent_id):
                    uid = str(uuid4())
                    mdb.execute('insert into universes (id, parent_id) values (?, ?)', [uid, parent_id])
                    self.__universe_db_connect(uid)
                    udb: Connection = self.__universe_dbs[uid]
                    udb.executescript('''
                        create table actions (
                            tick integer not null,
                            subtick integer not null,
                            character_id text not null,
                            content text not null,
                            
                            primary key (tick, subtick, character_id)
                        );
                        create table perceptions (
                            tick integer not null,
                            subtick integer not null,
                            character_id text not null,
                            content text not null,
                            
                            primary key (tick, subtick, character_id)
                        );
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
                case (str(action_name), dict({'universe_id': str(uid)}) as payload):
                    udb: Connection = self.__universe_dbs[uid]
                    match action_name:
                        case 'CreateLocation':
                            udb.execute(
                                'insert into locations (name, description) values (?, ?)',
                                [
                                    payload['name'],
                                    payload['description']
                                ]
                            )
                        case 'ConnectLocations':
                            from_name = payload['from_name']
                            to_name = payload['to_name']
                            travel_time = payload['travel_time']
                            if from_name == to_name:
                                raise Exception('Cannot connect location to itself')
                            if travel_time < 0:
                                raise Exception('Travel time cannot be less than zero')
                            udb.executemany(
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
                            cursor = udb.execute(
                                'select count(name) from locations where name = ?',
                                [payload['location_name']]
                            )
                            if cursor.fetchone()[0] == 0:
                                raise Exception('Location not found')

                    logging.debug({
                        'event_type': 'STORE_ACTION',
                        'tick': self.__tick,
                        'subtick': self.__subtick,
                        'value': {'kind': kind, 'payload': payload}
                    })
                    self.__subtick = self.__subtick + 1

        except Exception as e:
            # TODO send error message back to user
            # TODO implement messaging

            logging.error({
                'event_type': 'APPLY_ERROR',
                'tick': self.__tick,
                'subtick': self.__subtick,
                'value': {'error': e, 'kind': kind, 'payload': payload}
            })

    def commit(self) -> None:
        next_tick: int = self.__multiverse_db.execute('''
            update properties set value = value + 1 where name = 'tick' returning value
        ''').fetchone()[0]
        self.__multiverse_db.commit()
        for row in self.__multiverse_db.execute('select id from universes').fetchall():
            self.__universe_dbs[row[0]].commit()
        self.__tick = next_tick


class TestMultiverseApply(unittest.TestCase):
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
        self.multiverse.apply('CreateUniverse', None)
        self.multiverse.commit()
        uid: str = self.__fetch_universe_id()
        # then zeroth universe db is created
        with self.__universe_db(uid) as udb:
            self.assertEqual(
                ('empty',),
                udb.execute("select 'empty'").fetchone()
            )
        # and first db is not created yet
        with self.assertRaises(Exception):
            self.__universe_db('i_dont_exist')

    def test_create_location(self):
        # given
        self.multiverse.apply('CreateUniverse', None)
        self.multiverse.commit()
        uid: str = self.__fetch_universe_id()
        # when
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        self.multiverse.commit()
        # then
        with self.__universe_db(uid) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )
        # when a location with duplicate name is added
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'Strezhevoy', 'description': 'Some other description'}
        )
        self.multiverse.commit()
        # then nothing is changed
        with self.__universe_db(uid) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )

    def test_connect_locations(self):
        # given
        self.multiverse.apply('CreateUniverse', None)
        self.multiverse.commit()
        uid: str = self.__fetch_universe_id()
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'Beijing', 'description': 'The capital of China'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'London', 'description': 'The capital of the UK'}
        )
        # when
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': uid, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 3510}
        )
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': uid, 'from_name': 'Strezhevoy', 'to_name': 'London', 'travel_time': 6000}
        )
        self.multiverse.commit()
        # then
        with self.__universe_db(uid) as udb:
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
            {'universe_id': uid, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 9000}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.__universe_db(uid) as udb:
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
            {'universe_id': uid, 'from_name': 'Strezhevoy', 'to_name': 'Strezhevoy', 'travel_time': 100500}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.__universe_db(uid) as udb:
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
            {'universe_id': uid, 'from_name': 'London', 'to_name': 'Beijing', 'travel_time': -2}
        )
        self.multiverse.commit()
        # then nothing changes
        with self.__universe_db(uid) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                udb.execute('select from_name, to_name, travel_time, ordinal from directions').fetchall()
            )

    def test_create_character(self):
        # given
        self.multiverse.apply('CreateUniverse', None)
        self.multiverse.commit()
        uid: str = self.__fetch_universe_id()
        self.multiverse.apply('CreatePlayer', 'player1')
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': uid, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        # when
        self.multiverse.apply(
            'CreateCharacter',
            {'universe_id': uid, 'player_id': 'player1', 'location_name': 'Strezhevoy'}
        )
        self.multiverse.commit()
        # then
        # TODO

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

    # independent universe DB accessor
    def __universe_db(self, universe_id: str) -> Connection:
        path = f'{self.multiverse.instance_id}/{universe_id}.db'
        # In the tests we really want to fail,
        # if the requested database does not exist.
        if not os.path.isfile(path):
            raise Exception(f'No such database: {path}')
        # noinspection PyTypeChecker
        return closing(sqlite3.connect(path))

    def __fetch_universe_id(self):
        return self.multiverse_db.execute('select id from universes').fetchone()[0]


if __name__ == '__main__':
    unittest.main()
