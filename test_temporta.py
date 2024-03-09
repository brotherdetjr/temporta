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

from temporta import Multiverse


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
