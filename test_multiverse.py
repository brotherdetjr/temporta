from __future__ import annotations

import json
import os
import shutil
import sqlite3
import unittest
from contextlib import closing
from sqlite3 import Connection
from typing import Any
from uuid import uuid4

from actions import CreatePlayer, CreateUniverse, CreateLocation, ConnectLocations, CreateCharacter
from multiverse import Multiverse


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
            self.mdb_all('select name, value from properties')
        )

    def test_create_player(self):
        # expect
        self.assertEqual(
            [('root',)],
            self.mdb_all('select id from players')
        )
        # when
        self.multiverse.apply(CreatePlayer('player1'))
        self.multiverse.apply(CreatePlayer('player2'))
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb_all('select id from players')
        )
        # when duplicate is requested
        self.multiverse.apply(CreatePlayer('player2'))
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb_all('select id from players')
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply(CreateUniverse())
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
        self.multiverse.apply(CreateUniverse())
        # when
        self.multiverse.apply(CreateLocation('Strezhevoy', 1, 'The best town in the world'))
        self.multiverse.commit()
        # then
        with self.udb(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )
        # when a location with duplicate name is added
        self.multiverse.apply(CreateLocation('Strezhevoy', 1, 'The best town in the world'))
        self.multiverse.commit()
        # then nothing is changed
        with self.udb(1) as udb:
            self.assertEqual(
                [('Strezhevoy', 'The best town in the world')],
                udb.execute('select name, description from locations').fetchall()
            )

    def test_connect_locations(self):
        # given
        self.multiverse.apply(CreateUniverse())
        self.multiverse.apply(CreateLocation('Strezhevoy', 1, 'The best town in the world'))
        self.multiverse.apply(CreateLocation('Beijing', 1, 'The capital of China'))
        self.multiverse.apply(CreateLocation('London', 1, 'The capital of the UK'))
        # when
        self.multiverse.apply(ConnectLocations('Strezhevoy', 'Beijing', 1, 3510))
        self.multiverse.apply(ConnectLocations('Strezhevoy', 'London', 1, 6000))
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
        self.multiverse.apply(ConnectLocations('Strezhevoy', 'Beijing', 1, 9000))
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
        self.multiverse.apply(ConnectLocations('Strezhevoy', 'Strezhevoy', 1, 100500))
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
        self.multiverse.apply(ConnectLocations('London', 'Beijing', 1, -2))
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
        self.assertEqual(0, self.mdb_one("select value from properties where name='tick'")[0])
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(1, self.mdb_one("select value from properties where name='tick'")[0])
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(2, self.mdb_one("select value from properties where name='tick'")[0])

    # TODO test for CreateCharacter
    def test_record_action(self):
        # given
        self.multiverse.apply(CreateUniverse())
        self.multiverse.apply(CreatePlayer('player1'))
        self.multiverse.apply(CreatePlayer('player2'))
        self.multiverse.apply(CreateCharacter('player1', 1))
        self.multiverse.apply(CreateCharacter('player2', 1))
        self.multiverse.commit()
        # when
        self.multiverse.record_action(42, CreateLocation('Tbilisi', 1, 'The capital of Georgia'))
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': None,
                    'payload': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                }
            ],
            self.fetch_actions()
        )
        # when
        self.multiverse.record_action(9000, CreateLocation('London', 1, 'The capital of the UK'))
        self.multiverse.record_action(9001, ConnectLocations('London', 'Tbilisi', 1, 33))
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': None,
                    'payload': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9000,
                    'character_id': None,
                    'payload': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'name': 'London',
                        'description': 'The capital of the UK'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9001,
                    'character_id': None,
                    'payload': {
                        'kind': 'ConnectLocations',
                        'from_name': 'London',
                        'to_name': 'Tbilisi',
                        'travel_time': 33,
                        'universe_id': 1
                    }
                }
            ],
            self.fetch_actions()
        )

    def fetch_actions(self) -> list[Any]:
        with self.multiverse_db as mdb:
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

    def mdb_one(self, sql: str, *args) -> tuple[any]:
        return self.multiverse_db.execute(sql, args).fetchone()

    def mdb_all(self, sql: str, *args) -> list[any]:
        return self.multiverse_db.execute(sql, args).fetchall()


if __name__ == '__main__':
    unittest.main()
