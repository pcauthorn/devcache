import unittest
from copy import deepcopy
from io import StringIO
from unittest import mock
from unittest.mock import create_autospec
from unittest.mock import patch
from devcache import devcache
from devcache.cache import _get_function_arg_str
from devcache.storage import MemoryStore
from devcache.utils import update_dicts


def with_args(a, b, c):
    pass


def with_kwargs(x=None, y=None, z=None):
    pass


def with_both(arg1, arg2, kwarg1=None, kwarg2=None):
    pass


class Md5Patch:

    def __init__(self, data):
        self.data = data

    def hexdigest(self):
        if not self.data:
            return 'None'
        return self.data.decode("utf-8")


class TestGetArgs(unittest.TestCase):

    def setUp(self):
        self.md5_patch = patch('devcache.cache.md5', Md5Patch)
        self.md5_patch.start()

    def tearDown(self):
        self.md5_patch.stop()

    def obj_method(self, a, b, c):
        pass

    def test_obj_method(self):
        self.assertEqual('(a=1, b=2, c=3)', _get_function_arg_str(self.obj_method,
                                                                  [self, 1, 2, 3],
                                                                  {},
                                                                  ['a', 'b', 'c'],
                                                                  None))

    def test_use_all(self):
        self.assertEqual('(a=x, b=y, c=z)', _get_function_arg_str(with_args, ['x', 'y', 'z'], {}, None, []))
        self.assertEqual('(x=_X_, y=_Y_, z=None)',
                         _get_function_arg_str(with_kwargs, [], {'x': '_X_', 'y': '_Y_'}, None, []))
        self.assertEqual('(arg1=v1, arg2=v2, kwarg1=1, kwarg2=2)',
                         _get_function_arg_str(with_both, ['v1', 'v2'], {'kwarg1': 1, 'kwarg2': 2}, None, []))

    def test_no_args(self):
        self.assertEqual('()', _get_function_arg_str(with_args, [], {}, [], None))
        self.assertEqual('()', _get_function_arg_str(with_kwargs, [], {}, [], None))
        self.assertEqual('()', _get_function_arg_str(with_both, [], {}, [], None))

    def test_use_some(self):
        self.assertEqual('(a=first)', _get_function_arg_str(with_args,
                                                            ['first', 'second', 'third'],
                                                            {'hello': 1},
                                                            ['a'],
                                                            None))
        self.assertEqual('(arg1=arg1v, kwarg1=v)',
                         _get_function_arg_str(with_both, ['arg1v'], {'kwarg1': 'v'}, ['arg1', 'kwarg1'], None))

    def test_ignore_some(self):
        self.assertEqual('(c=3)', _get_function_arg_str(with_args, ['1', '2', '3'], None, None, ['a', 'b']))
        self.assertEqual('(x=3, y=2)', _get_function_arg_str(with_kwargs, None, {'x': 3, 'y': 2}, None, ['z']))
        self.assertEqual('(arg2=hello, kwarg2=kw2)',
                         _get_function_arg_str(with_both,
                                               ['yo', 'hello'],
                                               {'kwarg1': 'kw1', 'kwarg2': 'kw2'},
                                               None,
                                               ['arg1', 'kwarg1']))

    def test_wrong_args(self):
        self.assertEqual('()', _get_function_arg_str(with_args, {}, [], ['a1', 'b1'], ['yes', 'yep']))


class TestUpdateDicts(unittest.TestCase):

    def test_simple(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        copy_o = deepcopy(o)
        copy_t = deepcopy(t)
        c = update_dicts(o, t)
        copy_o.update(copy_t)
        self.assertEqual(c, copy_o)

    def test_recursive_negative_case(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        n1 = {5: 'e', 6: 'f', 'n': o}
        n2 = {5: 'f', 6: 'f', 'n': t}
        c = update_dicts(n1, n2)
        n1.update(n2)
        self.assertNotEqual(c, n1)

    def test_recursive(self):
        o = {1: 'a', 2: 'b'}
        t = {2: 'c', 4: 'd'}
        n1 = {5: 'e', 6: 'f', 'n': o}
        n2 = {5: 'f', 6: 'f', 'n': t}
        c = update_dicts(n1, n2)
        n2.pop('n')
        n1.update(n2)
        o.update(t)
        self.assertEqual(c, n1)

    def test_update_multiple_dicts(self):
        one = {1: 'a', 2: 'b'}
        two = {2: 'c', 3: 'd'}
        three = {2: 'e', 4: 'f'}
        test = deepcopy(one)
        test.update(two)
        test.update(three)
        c = update_dicts(one, two, three)
        self.assertEqual(c, test)


class TestCacheDecorator(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.stash = mock.patch('devcache.cache.stash', self.store)
        self.stash.start()
        self.mock = mock.Mock()
        self.mock.__qualname__ = 'qualname'
        self.mock.__name__ = 'unit_test'

    def tearDown(self):
        self.stash.stop()

    def test_enabled(self):
        f = StringIO('''
enabled: true
props:
    1: 
        group: test
        use_cache: true 

        ''')

        decorated = devcache(config_file=f, group='test')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.mock.assert_called_once()

    def test_not_enabled(self):
        f = StringIO('''
enabled: false
props:
    1: 
        group: test
        use_cached: true 
''')

        decorated = devcache(config_file=f, group='test')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 2)

    def test_use_cache(self):
        f = StringIO('''
props:
    1:
        group: test
        use_cache: true
                ''')
        decorated = devcache(config_file=f, group='test')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)
        self.mock.reset_mock()
        f = StringIO('''
props:
    1: 
        group: test2
        use_cache: false
                ''')
        decorated = devcache(config_file=f, group='test2')(self.mock)
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 2)

    def test_reset(self):
        f = StringIO('''
reset: true
props:
    1: 
        group: one
        use_cache: true
                ''')
        decorated = devcache(config_file=f, group='one')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)

    def test_key_prefix(self):
        f = StringIO('''
key_prefix: 'yo'
props:
    1: 
        group: one
        use_cache: true
                        ''')
        decorated = devcache(config_file=f, group='one')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello again')
        self.assertTrue(all([x.startswith('yo') for x in self.store.data]))


class TestMatching(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.stash = mock.patch('devcache.cache.stash', self.store)
        self.stash.start()
        self.mock = mock.Mock()
        self.mock.__qualname__ = 'qualname'
        self.mock.__name__ = 'unit_test_get_overrides'

    def test_group(self):
        f = StringIO("""
props:
    0: 
        group: diff
        use_cache: false
    1: 
        group: one
        use_cache: true
            """)
        decorated = devcache(config_file=f, group='one')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)

    def test_patterns(self):
        f = StringIO("""
props:
    0: 
        pattern: '.*unit_test_get_overrides.*'
        use_cache: true
    1: 
        group: one
        use_cache: false
            """)
        decorated = devcache(config_file=f, group='one')(self.mock)
        self.mock.return_value = 3
        decorated('hello')
        decorated('hello')
        self.assertEqual(self.mock.call_count, 1)

    def test_method_key_args(self):
        f = StringIO("""
props:
    0: 
        group: one
        use_cache: true
            """)
        mock_function = create_autospec(with_both, return_value='whateva')
        decorated = devcache(config_file=f, key_args=['arg1'], group='one')(mock_function)
        decorated('hello', 'whatever', kwarg1='yo')
        decorated('hello2', 'whatever', kwarg2='yo2')
        self.assertEqual(mock_function.call_count, 2)

        decorated('hello', 'whatever', 'yo')
        decorated('hello2', 'whatever2', 'yo2')
        self.assertEqual(mock_function.call_count, 2)

    def test_method_ignore_key_args(self):
        f = StringIO("""
props:
    0: 
        group: one
        use_cache: true

            """)
        mock_function = create_autospec(with_both, return_value='whateva')
        decorated = devcache(config_file=f, group='one', ignore_key_args=['kwarg1'])(mock_function)
        mock_function.return_value = 3
        decorated('hello', 'arg2', kwarg1='yo')
        decorated('hello', 'arg2', kwarg1='sup')
        self.assertEqual(mock_function.call_count, 1)
        decorated('hi', 'arg2', kwarg1='sup')
        self.assertEqual(mock_function.call_count, 2)


if __name__ == '__main__':
    unittest.main()
