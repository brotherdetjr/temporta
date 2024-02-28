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


class Multiverse:
    instance_id: str
    __multiverse_db: Connection
    __universe_dbs: Dict[int, Connection] = {}

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id

    @property
    def universes_path(self):
        return f'{self.instance_id}/universes'

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
                create table characters (
                    id text primary key,
                    player_id text,
                    universe_id integer,
                    location_name text,

                    unique (id, player_id),
                    foreign key (player_id) references players (id)
                );
            ''')
        Path(self.universes_path).mkdir(parents=True, exist_ok=True)
        for universe_id in self.__universe_ids():
            self.__universe_db_connect(universe_id)
        return self

    def __exit__(self, *args) -> None:
        for _, value in self.__universe_dbs.items():
            value.close()
        self.__multiverse_db.close()

    def __universe_ids(self) -> list[int]:
        return list[int](map(lambda n: int(n), os.listdir(self.universes_path)))

    def __universe_db_connect(self, universe_id: int) -> None:
        conn = sqlite3.connect(f'{self.universes_path}/{universe_id}')
        conn.execute('pragma foreign_keys = 1')
        self.__universe_dbs[universe_id] = conn

    def apply(self, kind: str, payload: dict[str, str | int] | str | None = None) -> None:
        mdb = self.__multiverse_db
        try:
            match (kind, payload):
                case ('CreatePlayer', str(player_id)):
                    mdb.execute('insert into players (id) values (?)', [player_id])
                    mdb.commit()
                case ('CreateUniverse', None):
                    ids = self.__universe_ids()
                    universe_id: int = 0 if not len(ids) else max(ids) + 1
                    self.__universe_db_connect(universe_id)
                    udb: Connection = self.__universe_dbs[universe_id]
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
                    udb.commit()
                case (str(action_name), dict({'universe_id': int(universe_id)}) as payload):
                    udb: Connection = self.__universe_dbs[universe_id]
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
                            mdb.execute(
                                '''
                                    insert into characters (id, player_id, universe_id, location_name)
                                    values (?, ?, ?, ?)
                                ''',
                                [
                                    str(uuid4()),
                                    payload['player_id'],
                                    universe_id,
                                    payload['location_name']
                                ]
                            )
                    udb.commit()
            mdb.commit()

        except Exception as e:
            # TODO send error message back to user
            # TODO implement messaging

            logging.error([e, kind, payload])


class TestMultiverseApply(unittest.TestCase):
    multiverse: Multiverse
    multiverse_db: Connection  # independent sqlite3 connection for tests

    def setUp(self):
        self.multiverse = Multiverse(str(uuid4()))
        self.multiverse.__enter__()
        self.multiverse_db = sqlite3.connect(f'{self.multiverse.instance_id}/multiverse.db')

    def tearDown(self):
        self.multiverse.__exit__()
        self.multiverse_db.close()
        shutil.rmtree(self.multiverse.instance_id)

    def test_create_player(self):
        # when
        self.multiverse.apply('CreatePlayer', 'player1')
        self.multiverse.apply('CreatePlayer', 'player2')
        # then
        self.assertEqual(
            [('player1',), ('player2',)],
            list(self.multiverse_db.execute('select id from players'))
        )
        # when duplicate is requested
        self.multiverse.apply('CreatePlayer', 'player2')
        # then no changes happen
        self.assertEqual(
            [('player1',), ('player2',)],
            list(self.multiverse_db.execute('select id from players'))
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply('CreateUniverse')
        # then zeroth universe db is created
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [('empty',)],
                list(udb.execute("select 'empty'"))
            )
        # and first db is not created yet
        with self.assertRaises(Exception):
            self.__universe_db(1)

    def test_create_location(self):
        # given
        self.multiverse.apply('CreateUniverse')
        # when
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        # then
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                list(udb.execute('select name, description from locations'))
            )
        # when a location with duplicate name is added
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'Strezhevoy', 'description': 'Some other description'}
        )
        # then nothing is changed
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                list(udb.execute('select name, description from locations'))
            )

    def test_connect_locations(self):
        # given
        self.multiverse.apply('CreateUniverse')
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'Beijing', 'description': 'The capital of China'}
        )
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'London', 'description': 'The capital of the UK'}
        )
        # when
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 0, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 3510}
        )
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 0, 'from_name': 'Strezhevoy', 'to_name': 'London', 'travel_time': 6000}
        )
        # then
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                list(udb.execute('select from_name, to_name, travel_time, ordinal from directions'))
            )
        # when inserting duplicate
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 0, 'from_name': 'Strezhevoy', 'to_name': 'Beijing', 'travel_time': 9000}
        )
        # then nothing changes
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                list(udb.execute('select from_name, to_name, travel_time, ordinal from directions'))
            )
        # when linking to itself
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 0, 'from_name': 'Strezhevoy', 'to_name': 'Strezhevoy', 'travel_time': 100500}
        )
        # then nothing changes
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                list(udb.execute('select from_name, to_name, travel_time, ordinal from directions'))
            )
        # when linking with negative travel time
        self.multiverse.apply(
            'ConnectLocations',
            {'universe_id': 0, 'from_name': 'London', 'to_name': 'Beijing', 'travel_time': -2}
        )
        # then nothing changes
        with self.__universe_db(0) as udb:
            self.assertEqual(
                [
                    ('Strezhevoy', 'Beijing', 3510, 0),
                    ('Beijing', 'Strezhevoy', 3510, 0),
                    ('Strezhevoy', 'London', 6000, 1),
                    ('London', 'Strezhevoy', 6000, 0)
                ],
                list(udb.execute('select from_name, to_name, travel_time, ordinal from directions'))
            )

    def test_create_character(self):
        # given
        self.multiverse.apply('CreateUniverse')
        self.multiverse.apply('CreatePlayer', 'player1')
        self.multiverse.apply(
            'CreateLocation',
            {'universe_id': 0, 'name': 'Strezhevoy', 'description': 'The best town in the world'}
        )
        # when
        self.multiverse.apply(
            'CreateCharacter',
            {'universe_id': 0, 'player_id': 'player1', 'location_name': 'Strezhevoy'}
        )
        # then
        self.assertEqual(
            [('player1', 0, 'Strezhevoy')],
            list(self.multiverse_db.execute('select player_id, universe_id, location_name from characters'))
        )
        # when universe does not exist
        self.multiverse.apply(
            'CreateCharacter',
            {'universe_id': 42, 'player_id': 'ignore', 'location_name': 'ignore'}
        )
        # then universe is not created
        with self.assertRaises(Exception):
            self.__universe_db(42)
        # when location does not exist
        self.multiverse.apply(
            'CreateCharacter',
            {'universe_id': 0, 'player_id': 'player1', 'location_name': 'Beijing'}
        )
        # then character is not created
        self.assertEqual(
            [('player1', 0, 'Strezhevoy')],
            list(self.multiverse_db.execute('select player_id, universe_id, location_name from characters'))
        )

    # independent universe DB accessor
    def __universe_db(self, dbid: int) -> Connection:
        path = f'{self.multiverse.instance_id}/universes/{dbid}'
        # In the tests we really want to fail,
        # if the requested database does not exist.
        if not os.path.isfile(path):
            raise Exception(f'No such database: {path}')
        # noinspection PyTypeChecker
        return closing(sqlite3.connect(path))


if __name__ == '__main__':
    unittest.main()
