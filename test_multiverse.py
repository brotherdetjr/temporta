from __future__ import annotations

import json
import os
import shutil
import unittest
from typing import Any
from uuid import uuid4

from actions import CreatePlayer, CreateUniverse, CreateLocation, ConnectLocations, CreateCharacter
from multiverse import Multiverse
from testutil import Conn


class TestMultiverse(unittest.TestCase):
    multiverse: Multiverse
    mdb: Conn  # independent sqlite3 connection for tests
    udbs: dict[int, Conn]

    def setUp(self):
        self.multiverse = Multiverse('.test-' + str(uuid4()))
        self.multiverse.__enter__()
        self.mdb = Conn(f'{self.multiverse.instance_id}/multiverse.db')
        self.udbs = {}

    def tearDown(self):
        self.multiverse.__exit__()
        self.mdb.close()
        for _, udb in self.udbs.items():
            udb.close()
        shutil.rmtree(self.multiverse.instance_id)

    def test_create_multiverse(self):
        # expect
        self.assertEqual(
            [('tick', 0)],
            self.mdb.all('select name, value from properties')
        )

    def test_create_player(self):
        # expect
        self.assertEqual(
            [('root',)],
            self.mdb.all('select id from players')
        )
        # when
        self.multiverse.apply(CreatePlayer(player_id='player1'))
        self.multiverse.apply(CreatePlayer(player_id='player2'))
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb.all('select id from players')
        )
        # when duplicate is requested
        self.multiverse.apply(CreatePlayer(player_id='player2'))
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb.all('select id from players')
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply(CreateUniverse())
        self.multiverse.commit()
        # then first universe db is created
        self.assertEqual(
            ('empty',),
            self.udb(1).one("select 'empty'")
        )
        # and 100500th db is not created yet
        with self.assertRaises(Exception):
            self.udb(100500)

    def test_create_location(self):
        # given
        self.multiverse.apply(CreateUniverse())
        # when
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world')
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('Strezhevoy', 'The best town in the world')],
            self.udb(1).all('select name, description from locations')
        )
        # when a location with duplicate name is added
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world')
        )
        self.multiverse.commit()
        # then nothing is changed
        self.assertEqual(
            [('Strezhevoy', 'The best town in the world')],
            self.udb(1).all('select name, description from locations')
        )

    def test_connect_locations(self):
        # given
        self.multiverse.apply(CreateUniverse())
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world')
        )
        self.multiverse.apply(
            CreateLocation(name='Beijing', universe_id=1, description='The capital of China')
        )
        self.multiverse.apply(
            CreateLocation(name='London', universe_id=1, description='The capital of the UK')
        )
        # when
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='Beijing', universe_id=1, travel_time=3510)
        )
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='London', universe_id=1, travel_time=6000)
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                ('Strezhevoy', 'Beijing', 3510, 0),
                ('Beijing', 'Strezhevoy', 3510, 0),
                ('Strezhevoy', 'London', 6000, 1),
                ('London', 'Strezhevoy', 6000, 0)
            ],
            self.udb(1).all('select from_name, to_name, travel_time, ordinal from directions')
        )
        # when inserting duplicate
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='Beijing', universe_id=1, travel_time=9000)
        )
        self.multiverse.commit()
        # then nothing changes
        self.assertEqual(
            [
                ('Strezhevoy', 'Beijing', 3510, 0),
                ('Beijing', 'Strezhevoy', 3510, 0),
                ('Strezhevoy', 'London', 6000, 1),
                ('London', 'Strezhevoy', 6000, 0)
            ],
            self.udb(1).all('select from_name, to_name, travel_time, ordinal from directions')
        )
        # when linking to itself
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='Strezhevoy', universe_id=1, travel_time=100500)
        )
        self.multiverse.commit()
        # then nothing changes
        self.assertEqual(
            [
                ('Strezhevoy', 'Beijing', 3510, 0),
                ('Beijing', 'Strezhevoy', 3510, 0),
                ('Strezhevoy', 'London', 6000, 1),
                ('London', 'Strezhevoy', 6000, 0)
            ],
            self.udb(1).all('select from_name, to_name, travel_time, ordinal from directions')
        )
        # when linking with negative travel time
        self.multiverse.apply(
            ConnectLocations(from_name='London', to_name='Beijing', universe_id=1, travel_time=-2)
        )
        self.multiverse.commit()
        # then nothing changes
        self.assertEqual(
            [
                ('Strezhevoy', 'Beijing', 3510, 0),
                ('Beijing', 'Strezhevoy', 3510, 0),
                ('Strezhevoy', 'London', 6000, 1),
                ('London', 'Strezhevoy', 6000, 0)
            ],
            self.udb(1).all('select from_name, to_name, travel_time, ordinal from directions')
        )

    def test_commit(self):
        # expect
        self.assertEqual(0, self.mdb.one("select value from properties where name='tick'")[0])
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(1, self.mdb.one("select value from properties where name='tick'")[0])
        # when
        self.multiverse.commit()
        # then
        self.assertEqual(2, self.mdb.one("select value from properties where name='tick'")[0])

    # TODO test for CreateCharacter
    def test_record_action(self):
        # given
        self.multiverse.apply(CreateUniverse())
        self.multiverse.apply(CreatePlayer(player_id='player1'))
        self.multiverse.apply(CreatePlayer(player_id='player2'))
        self.multiverse.apply(CreateCharacter(player_id='player1', universe_id=1))
        self.multiverse.apply(CreateCharacter(player_id='player2', universe_id=1))
        self.multiverse.commit()
        # when
        self.multiverse.record_action(
            42,
            CreateLocation(name='Tbilisi', universe_id=1, description='The capital of Georgia')
        )
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
        self.multiverse.record_action(
            9000,
            CreateLocation(name='London', universe_id=1, description='The capital of the UK')
        )
        self.multiverse.record_action(
            9001,
            ConnectLocations(from_name='London', to_name='Tbilisi', universe_id=1, travel_time=33)
        )
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
        rows: list[Any] = self.mdb.all(
            '''
                select tick, subtick, character_id, payload
                from actions order by tick, subtick
            '''
        )
        return list(map(lambda row: {
            'tick': row[0],
            'subtick': row[1],
            'character_id': row[2],
            'payload': json.loads(row[3])
        }, rows))

    # independent universe DB accessor
    def udb(self, universe_id: int) -> Conn:
        if universe_id in self.udbs:
            return self.udbs[universe_id]
        path = f'{self.multiverse.instance_id}/{universe_id}.db'
        # In the tests we really want to fail,
        # if the requested database does not exist.
        if not os.path.isfile(path):
            raise Exception(f'No such database: {path}')
        # noinspection PyTypeChecker
        conn = Conn(path)
        self.udbs[universe_id] = conn
        return conn


if __name__ == '__main__':
    unittest.main()
