import inspect
import logging
import os
import re
import sys
from copy import copy
from functools import wraps
from hashlib import md5

import yaml

from devcache.storage import SqliteStore

logging.basicConfig()
logger = logging.getLogger(__name__)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

DEFAULT_DIR = os.path.expanduser(r'~\.devcache')

DEFAULT_CONFIG = os.path.join(DEFAULT_DIR, 'devcache.yaml')

stash = SqliteStore(DEFAULT_DIR)

configs = {}


def get_config(file_name):
    if isinstance(file_name, str):
        config = configs.get(file_name)
        if not config:
            try:
                with open(file_name) as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                logger.warning(f'Could not load file_name: {file_name}.  Disabling')
                config = {'enabled': False}
    else:
        try:
            config = yaml.safe_load(file_name)
        except Exception as e:
            logger.warning(f'Could not load supplied file: {file_name}.  Disabling')
            config = {'enabled': False}
    configs[file_name] = config
    return config


def _resolve_props(config, function_group, key):
    for k, v in sorted(config.get('props', {}).items()):
        valid_keys = {'enabled', 'use_cache', 'group', 'pattern'}
        extra_keys = set(v.keys()) - valid_keys
        if extra_keys:
            logger.warning(f'{v} contains extra keys:  {",".join(extra_keys)}')
            logger.warning(f'Valid keys:  {",".join(valid_keys)}')
            logger.warning(f'Skipping...')
            continue
        group = v.get('group') or None
        pattern = v.get('pattern') or None
        enabled = v.get('enabled', True)
        if not enabled:
            logger.info(f'{v} not enabled... skipping')
            continue
        if group and group == function_group:
            if not pattern:
                return v
            try:
                if re.match(pattern, key):
                    return v
            except:
                logger.warning(f'Pattern {pattern} for rule {k}, failed.  Ignoring')

        if pattern:
            try:
                if re.match(pattern, key):
                    return v
            except:
                logger.warning(f'Pattern {pattern} for rule {k}, failed.  Ignoring')

    return {}


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


def devcache(config_file=None, group=None, key_args=None, ignore_key_args=None):
    config = get_config(config_file or DEFAULT_CONFIG)

    def decorator(func):
        function_name = f'{func.__module__}.{func.__qualname__}.{func.__name__}'
        props = _resolve_props(config, group, function_name)
        if not props:
            logger.warning(f'Not props found for group/function_name:  {group}/{function_name}.  Not caching')
        enabled = config.get('enabled', True)
        key_prefix = config.get('key_prefix')
        logger.info(f'using props: {props} for group/function_name:  {group}/{function_name}')
        if enabled:
            enabled = props.get('enabled', True)
        use_cache = props.get('use_cache', True)
        refresh = config.get('refresh')
        if not props or not enabled:
            if not enabled:
                logger.info(f'stash_decorator not enabled. Not stashing')

            @wraps(func)
            def _pass(*args, **kwargs):
                return func(*args, **kwargs)

            return _pass

        @wraps(func)
        def wrap(*args, **kwargs):
            kp = f'{key_prefix}.' if key_prefix else ''
            args_str = _get_function_arg_str(func, args, kwargs, key_args, ignore_key_args)
            key = f'{kp}{function_name}{args_str}'

            if not refresh and use_cache and stash.exists(key):
                logger.info(f'retrieving {key} from cache')
                return stash.get(key)

            result = func(*args, **kwargs)
            logger.info(f'will stash to key (refresh: {refresh}): {key}. obj: {str(result)[:25]}')
            stash.store(key, result, tag=group)
            return result

        return wrap

    return decorator


if __name__ == '__main__':
    def test(a, b, hello='yo', sup=None):
        pass


    print(_get_function_arg_str(test, ('0', '1'), {'sup': 'sup yo'}, key_args=('a', 'hello')))
