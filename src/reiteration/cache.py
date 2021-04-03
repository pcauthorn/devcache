import inspect
import os
import re
from copy import copy
from functools import wraps
from hashlib import md5

from reiteration.storage import SqliteStore
from reiteration.utils import update_dicts, gattr, get_config

DEFAULT_DIR = os.path.expanduser('~/.reiteration')

stash = SqliteStore(DEFAULT_DIR)


class FileSections:
    Cached = 'cached'
    Defaults = 'defaults'
    Groups = 'groups'
    Methods = 'methods'


class Properties:
    Enabled = 'enabled'
    Use_Cache = 'use_cache'
    Verbose = 'verbose'
    Key_Prefix = 'key_prefix'
    Reset = 'reset'


class FunctionProperties:
    Ignore_Key_Args = 'ignore_key_args'
    Key_Args = 'key_args'
    MatchMultiple = 'match_multiple'


def _resolve_props(config, group, function_name):
    props = gattr(config, FileSections.Cached, FileSections.Defaults)
    group_overrides = gattr(config, FileSections.Cached, FileSections.Groups, default={}).get(group, {})
    function_overrides = _get_function_props(config, function_name)

    if Properties.Reset in group_overrides or Properties.Reset in function_overrides:
        print('Kwarg reset found in group_overrides, this is an override property only.  Ignoring')
        try:
            group_overrides.pop(Properties.Reset)
        except:
            pass
        try:
            function_overrides.pop(Properties.Reset)
        except:
            pass
    return update_dicts(props, group_overrides, function_overrides)


def _get_function_arg_str(func, function_args, function_kwargs, key_args=None, ignore_key_args=None, verbose=False):
    function_args = copy(function_args) or []
    function_kwargs = copy(function_kwargs) or {}
    # if ignore_key_args is [] want to include all parameters
    if not key_args and ignore_key_args is None:

        if verbose:
            print('key_args empty.  Not keying with any args')
        return '()'

    key_args = key_args or []
    ignore_key_args = ignore_key_args or []

    parameters = list(inspect.signature(func).parameters.values())
    if hasattr(func, '__self__'):
        function_args = function_args[1:]

    arg_to_value = {k.name: v for k, v in zip(parameters, function_args)}
    for param in parameters[len(function_args):]:
        if param.name in function_kwargs:
            arg_to_value[param.name] = function_kwargs[param.name]
        else:
            if param.default != inspect._empty:
                arg_to_value[param.name] = param.default
    if key_args:
        arg_to_value = {k: v for k, v in arg_to_value.items() if k in key_args}
    else:
        arg_to_value = {k: v for k, v in arg_to_value.items() if k not in ignore_key_args}

    result = []
    for k, v in arg_to_value.items():
        result.append(f'{k}={md5(str(v).encode("utf-8")).hexdigest()}')

    return f'({", ".join(result)})'


def _get_overrides(overrides, group_overrides, group):
    group_overrides = group_overrides.get(group) or {}
    return update_dicts(overrides, group_overrides)


def _get_function_props(config, function_name):
    functions = config.get('cached', {}).get('methods', {})
    function_configs = []
    for k, v in functions.items():
        if function_name.endswith(k) or re.match(k, function_name):
            if not function_configs:
                function_configs.append(v)
            elif v.get(FunctionProperties.MatchMultiple):
                function_configs.append(v)
            else:
                print(f'Ignoring multiple match on key: {k} for function config: {v}')
    return update_dicts({}, *function_configs)


def cache_decorator(config_file=None, group=None):
    config = get_config(config_file)

    def decorator(func):
        function_name = f'{func.__module__}.{func.__qualname__}.{func.__name__}'
        props = _resolve_props(config, group, function_name)
        reset = props.get(Properties.Reset)
        enabled = props.get(Properties.Enabled, True)
        use_cache = props.get(Properties.Use_Cache, True)
        verbose = props.get(Properties.Verbose, True)
        if verbose:
            print(f'Using props: {props}')
        if not enabled:
            if verbose:
                print(f'stash_decorator not enabled. Not stashing')

            @wraps(func)
            def _pass(*args, **kwargs):
                return func(*args, **kwargs)

            return _pass

        @wraps(func)
        def wrap(*args, **kwargs):
            function_name = f'{func.__module__}.{func.__qualname__}.{func.__name__}'
            props = _resolve_props(config, group, function_name)
            key_prefix = props.get(Properties.Key_Prefix)

            kp = key_prefix + '.' if key_prefix else ''
            key_args = props.get(FunctionProperties.Key_Args)
            ignore_key_args = props.get(FunctionProperties.Ignore_Key_Args)
            args_str = _get_function_arg_str(func, args, kwargs, key_args, ignore_key_args)
            key = f'{kp}{function_name}{args_str}'

            if not enabled:
                if verbose:
                    print('cache decorator not enabled')
                return func(*args, **kwargs)
            if not reset and use_cache and stash.exists(key):
                if verbose:
                    print(f'retrieving {key} from cache')
                return stash.get(key)
            result = func(*args, **kwargs)
            if verbose:
                print(f'will stash {key}')
            stash.store(key, result, tag=group)
            return result

        return wrap

    return decorator


if __name__ == '__main__':
    def test(a, b, hello='yo', sup=None):
        pass


    print(_get_function_arg_str(test, ('0', '1'), {'sup': 'sup yo'}, key_args=('a', 'hello')))
