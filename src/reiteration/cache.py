from stashed.stash import stash, exists, retrieve
import logging
from configutils.src import update_dicts
from functools import wraps

logger = logging.getLogger(__name__)


class DecoratorKwargs:
    Group = 'group'
    Enabled = 'enabled'
    Use_Cache = 'use_cache'
    Verbose = 'verbose'
    Key_Args = 'key_args'


def cache_decorator(group=None,
                    enabled=None,
                    use_cache=None,
                    verbose=None,
                    group_overrides=None,
                    key_args=None,
                    overrides=None):
    group_overrides = group_overrides or {}
    overrides = overrides or {}
    if not group:
        group = overrides.get(DecoratorKwargs.Group)
    group_overrides = group_overrides.get(group, {})
    params = update_dicts(overrides, group_overrides)
    if verbose:
        print(f'Overrides: {params}')
    if enabled is None:
        enabled = params.get(DecoratorKwargs.Enabled, True)
    if use_cache is None:
        use_cache = params.get(DecoratorKwargs.Use_Cache, True)
    if verbose is None:
        verbose = params.get(DecoratorKwargs.Verbose, False)
    if key_args is None:
        key_args = params.get(DecoratorKwargs.Key_Args, False)

    def decorator(func):
        key = f'{func.__module__}.{func.__qualname__}.{func.__name__}'

        @wraps(func)
        def wrap(*args, **kwargs):
            if not enabled:
                if verbose:
                    print('cache decorator not enabled')
                return func(*args, **kwargs)
            if use_cache and exists(key):
                if verbose:
                    print(f'retrieving {key} from cache')
                return retrieve(key)
            result = func(*args, **kwargs)
            if verbose:
                print(f'stashing {key}')
            stash(key, result, group=group)
            return result

        return wrap

    return decorator


if __name__ == '__main__':
    print('hello')
