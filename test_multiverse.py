from __future__ import annotations

import json
import logging
import os
import shutil
import unittest
from typing import Any
from uuid import uuid4

from actions import CreatePlayer, CreateUniverse, CreateLocation, ConnectLocations, CreateCharacter
from multiverse import Multiverse, ROOT_CHARACTER_ID
from testutil import Conn

# TODO remove
logging.basicConfig(level=logging.DEBUG)


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
        self.multiverse.apply(CreatePlayer(player_id='player1'), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreatePlayer(player_id='player2'), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb.all('select id from players')
        )
        # when duplicate is requested
        self.multiverse.apply(CreatePlayer(player_id='player2'), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb.all('select id from players')
        )
        # when making an authorized request
        self.multiverse.apply(CreatePlayer(player_id='player3'), 123)
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [('root',), ('player1',), ('player2',)],
            self.mdb.all('select id from players')
        )

    def test_create_universe(self):
        # when
        self.multiverse.apply(CreateUniverse(), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then first universe db is created
        self.assertEqual(
            [(1, None)],
            self.mdb.all('select id, parent_id from universes')
        )
        self.assertEqual(
            ('empty',),
            self.udb(1).one("select 'empty'")
        )
        # when making an authorized request
        self.multiverse.apply(CreateUniverse(), 123)
        self.multiverse.commit()
        # then no changes happen
        self.assertEqual(
            [(1, None)],
            self.mdb.all('select id, parent_id from universes')
        )

    def test_create_location(self):
        # given
        self.multiverse.apply(CreateUniverse(), ROOT_CHARACTER_ID)
        # when
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world'),
            ROOT_CHARACTER_ID
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [('Strezhevoy', 'The best town in the world')],
            self.udb(1).all('select name, description from locations')
        )
        # when a location with duplicate name is added
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world'),
            ROOT_CHARACTER_ID
        )
        self.multiverse.commit()
        # then nothing is changed
        self.assertEqual(
            [('Strezhevoy', 'The best town in the world')],
            self.udb(1).all('select name, description from locations')
        )
        # when making an authorized request
        self.multiverse.apply(
            CreateLocation(name='Tomsk', universe_id=1, description='Not my favourite city'),
            123
        )
        self.multiverse.commit()
        # then nothing is changed
        self.assertEqual(
            [('Strezhevoy', 'The best town in the world')],
            self.udb(1).all('select name, description from locations')
        )

    def test_connect_locations(self):
        # given
        self.multiverse.apply(CreateUniverse(), ROOT_CHARACTER_ID)
        self.multiverse.apply(
            CreateLocation(name='Strezhevoy', universe_id=1, description='The best town in the world'),
            ROOT_CHARACTER_ID
        )
        self.multiverse.apply(
            CreateLocation(name='Beijing', universe_id=1, description='The capital of China'),
            ROOT_CHARACTER_ID
        )
        self.multiverse.apply(
            CreateLocation(name='London', universe_id=1, description='The capital of the UK'),
            ROOT_CHARACTER_ID
        )
        # when
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='Beijing', universe_id=1, travel_time=3510),
            ROOT_CHARACTER_ID
        )
        self.multiverse.apply(
            ConnectLocations(from_name='Strezhevoy', to_name='London', universe_id=1, travel_time=6000),
            ROOT_CHARACTER_ID
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
            ConnectLocations(from_name='Strezhevoy', to_name='Beijing', universe_id=1, travel_time=9000),
            ROOT_CHARACTER_ID
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
            ConnectLocations(from_name='Strezhevoy', to_name='Strezhevoy', universe_id=1, travel_time=100500),
            ROOT_CHARACTER_ID
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
            ConnectLocations(from_name='London', to_name='Beijing', universe_id=1, travel_time=-2),
            ROOT_CHARACTER_ID
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
        # when making an authorized request
        self.multiverse.apply(
            ConnectLocations(from_name='London', to_name='Beijing', universe_id=1, travel_time=999),
            123
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

    def test_create_character(self):
        # given
        self.multiverse.apply(CreatePlayer(player_id='player1'), ROOT_CHARACTER_ID)
        self.multiverse.commit()

        # when making an authorized request
        self.multiverse.apply(CreateCharacter(player_id='player1'), 123)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when all-null character is requested
        self.multiverse.apply(CreateCharacter(player_id=None, universe_id=None, parent_id=None), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when both parent_id and player_id are not None
        self.multiverse.apply(CreateCharacter(player_id='player1', parent_id=0), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when
        self.multiverse.apply(CreateCharacter(player_id='root'), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when new character belongs to non-existent universe
        self.multiverse.apply(CreateCharacter(player_id='player1', universe_id=42), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when new character belongs to non-existent player
        self.multiverse.apply(CreateCharacter(player_id='i_dont_exist'), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when new character belongs to non-existent parent
        self.multiverse.apply(CreateCharacter(parent_id=3333), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then nothing is added to the table
        self.assertEqual(1, self.mdb.count('characters'))

        # when
        self.multiverse.apply(CreateCharacter(player_id='player1'), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                (0, 'root', None, None),
                (1, 'player1', None, None)
            ],
            self.mdb.all('select id, player_id, universe_id, parent_id from characters')
        )

        # when
        self.multiverse.apply(CreateUniverse(), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreateCharacter(parent_id=1, universe_id=1), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                (0, 'root', None, None),
                (1, 'player1', None, None),
                (2, None, 1, 1)
            ],
            self.mdb.all('select id, player_id, universe_id, parent_id from characters')
        )

    def test_record_action(self):
        # given
        self.multiverse.apply(CreateUniverse(), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreatePlayer(player_id='player1'), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreatePlayer(player_id='player2'), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreateCharacter(player_id='player1', universe_id=1), ROOT_CHARACTER_ID)
        self.multiverse.apply(CreateCharacter(player_id='player2', universe_id=1), ROOT_CHARACTER_ID)
        self.multiverse.commit()
        # when
        self.multiverse.record_action(
            42,
            0,
            CreateLocation(name='Tbilisi', universe_id=1, description='The capital of Georgia'),
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': 0,
                    'payload_json': {
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
            1,
            CreateLocation(name='London', universe_id=1, description='The capital of the UK')
        )
        self.multiverse.record_action(
            9001,
            2,
            ConnectLocations(from_name='London', to_name='Tbilisi', universe_id=1, travel_time=33)
        )
        self.multiverse.commit()
        # then
        self.assertEqual(
            [
                {
                    'tick': 1,
                    'subtick': 42,
                    'character_id': 0,
                    'payload_json': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'name': 'Tbilisi',
                        'description': 'The capital of Georgia'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9000,
                    'character_id': 1,
                    'payload_json': {
                        'kind': 'CreateLocation',
                        'universe_id': 1,
                        'name': 'London',
                        'description': 'The capital of the UK'
                    }
                },
                {
                    'tick': 2,
                    'subtick': 9001,
                    'character_id': 2,
                    'payload_json': {
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
                select tick, subtick, character_id, payload_json
                from actions order by tick, subtick
            '''
        )
        return list(map(lambda row: {
            'tick': row[0],
            'subtick': row[1],
            'character_id': row[2],
            'payload_json': json.loads(row[3])
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
