import inspect
import os
from collections import defaultdict
from collections.abc import Mapping
from copy import copy
from copy import deepcopy
from functools import wraps
from hashlib import md5

from reiteration.storage import SqliteStore

DEFAULT_DIR = os.path.expanduser('~/.reiteration')

stash = SqliteStore(DEFAULT_DIR)


class OverridableKwargs:
    Enabled = 'enabled'
    Use_Cache = 'use_cache'
    Verbose = 'verbose'
    Key_Prefix = 'key_prefix'
    # Ignore_Key_Args = 'ignore_key_args'  #These don't make sense right?
    # Key_Args = 'key_args'


class OverrideOnlyKwargs:
    Reset = 'reset'


def _update_dicts(base, the_update):
    if not isinstance(base, dict) or not isinstance(the_update, dict):
        raise TypeError(f'Both items should be dictionaries: {type(base)}, {type(the_update)}')
    base = deepcopy(base)
    for k, v in the_update.items():
        if isinstance(v, Mapping):
            i = base.get(k, {})
            if isinstance(i, Mapping):
                base[k] = _update_dicts(i, v)
            else:
                base[k] = v
        else:
            base[k] = v
    return base


def _no_cache_args(key_args):
    return isinstance(key_args, (tuple, list, set)) and len(key_args) == 0


def _get_key_args(func, key_args, ignore_key_args, arg_vals, kwargs_vals, verbose=False):
    arg_vals = copy(arg_vals) or []
    arg_vals = copy(arg_vals) or []

    kwargs_vals = copy(kwargs_vals) or {}
    offset = 0
    if hasattr(func, '__self__'):
        arg_vals = arg_vals[1:]
        offset = 1
    if _no_cache_args(key_args):
        if verbose:
            print('key_args set to empty list.  Not keying with any args')
        return '()'
    key_args = key_args or []
    ignore_key_args = ignore_key_args or []

    spec = inspect.getfullargspec(func)
    border = None if not spec.defaults else len(spec.defaults)
    arg_names = spec.args[offset:border]
    kwarg_names = spec.args[border:]
    args = []

    use_args = defaultdict(lambda: False) if key_args else defaultdict(lambda: True)
    for index, arg in enumerate(arg_names):
        if arg in ignore_key_args:
            use_args[index] = False

        if arg in key_args:
            use_args[index] = True

    for kwarg in kwarg_names:
        if kwarg in ignore_key_args:
            use_args[kwarg] = False

        if kwarg in key_args:
            use_args[kwarg] = True

    # This relies on the fact that all kwargs are strings and names have to be unique across args and kwargs
    use_args.update({k: False for k in ignore_key_args})

    for index, arg in enumerate(arg_vals):
        if not use_args[index]:
            continue
        args.append(md5(str(arg).encode("utf-8")).hexdigest())
    for k, v in kwargs_vals.items():
        if not use_args[k]:
            continue
        args.append(f'{k} = {md5(str(v).encode("utf-8")).hexdigest()}')
    return f'({", ".join(args)})'


#
# def _get_arg_map(func, key_args, ignore_key_args, arg_vals, kwargs_vals, verbose=False):
#     arg_vals = copy(arg_vals) or []
#     kwargs_vals = copy(kwargs_vals) or {}
#     offset = 0

#
#     argspec = inspect.getfullargspec(func)
#     args_map = {k: v for k, v in zip(argspec.args[offset:], arg_vals)}
#     args_map.update(kwargs_vals)
#     if verbose:
#         print(f'All method args {",".join(args_map.keys())}')
#
#     if _no_cache_args(key_args):
#         if verbose:
#             print('key_args set to empty list.  Not keying with any args')
#         use_kwargs = defaultdict(lambda: False)
#     else:
#         ignore_key_args = ignore_key_args or []
#         key_args = key_args or []
#         if verbose:
#             print(f'key_args, ignore_key_args: {key_args}, {ignore_key_args}')
#
#         use_kwargs = defaultdict(lambda: False) if key_args else defaultdict(lambda: True)
#         use_kwargs.update({k: True for k in key_args})
#         use_kwargs.update({k: False for k in ignore_key_args})
#     result = {k: v for k, v in args_map.items() if use_kwargs[k]}
#     if verbose:
#         print(f'Will key with: {",".join(result.keys())}')
#     return result
#
#
# def _get_arg_keys(arg_map):
#     d = [f'{k} = {md5(str(v).encode("utf-8")).hexdigest()}' for k, v in arg_map.items()]
#     return f'({",".join(d)})'


def _get_overrides(overrides, group_overrides, group):
    group_overrides = group_overrides.get(group) or {}
    return _update_dicts(overrides, group_overrides)


def cache_decorator(group=None,
                    enabled=None,
                    use_cache=None,
                    verbose=None,
                    group_overrides=None,
                    key_args: list = None,
                    key_prefix=None,
                    ignore_key_args: list = None,
                    overrides=None):
    overrides = overrides or {}
    group_overrides = group_overrides or {}

    if OverrideOnlyKwargs.Reset in group_overrides:
        print('Kwarg reset found in group_overrides, this is an override property only.  Ignoring')

    reset = overrides.get(OverrideOnlyKwargs.Reset)
    overrides = _get_overrides(overrides, group_overrides, group)

    if enabled is None:
        enabled = overrides.get(OverridableKwargs.Enabled, True)
    if use_cache is None:
        use_cache = overrides.get(OverridableKwargs.Use_Cache, True)
    if verbose is None:
        verbose = overrides.get(OverridableKwargs.Verbose, True)
    if key_prefix is None:
        key_prefix = overrides.get(OverridableKwargs.Key_Prefix)

    if verbose:
        print(f'Used overrides: {overrides}')

    def decorator(func):
        if not enabled:
            if verbose:
                print(f'stash_decorator not enabled. Not stashing')

            @wraps(func)
            def _pass(*args, **kwargs):
                return func(*args, **kwargs)

            return _pass

        @wraps(func)
        def wrap(*args, **kwargs):
            kp = key_prefix + '.' if key_prefix else ''
            args_str = _get_key_args(func, key_args, ignore_key_args, args, kwargs)
            key = f'{kp}{func.__module__}.{func.__qualname__}.{func.__name__}{args_str}'

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
