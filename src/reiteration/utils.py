import os
from copy import deepcopy
from typing import Mapping

import yaml


def update_dicts(base, *the_updates):
    if not isinstance(base, dict) or not all([isinstance(x, dict) for x in the_updates]):
        raise TypeError(f'Args should be dictionaries: {type(base)}, {[type(x) for x in the_updates]}')
    base = deepcopy(base)
    for the_update in the_updates:
        for k, v in the_update.items():
            if isinstance(v, Mapping):
                i = base.get(k, {})
                if isinstance(i, Mapping):
                    base[k] = update_dicts(i, v)
                else:
                    base[k] = v
            else:
                base[k] = v
    return base


def gattr(obj, *args, callback=None, default=None, invoke_callables=False):
    cb = callback or (lambda x: x)
    try:
        for arg in args:
            if hasattr(obj, '__getitem__'):
                obj = obj[arg]
            else:
                obj = getattr(obj, arg)
                if invoke_callables and callable(obj):
                    obj = obj()
            if obj is None:
                return default
        return cb(obj)
    except (AttributeError, IndexError, KeyError, TypeError):
        return default


def get_config(config_file):
    if hasattr(config_file, 'read'):
        config = yaml.safe_load(config_file)
    else:
        if config_file and not (config_file.startswith('/') or config_file.startswith('\\')):
            config_file = os.path.join(os.path.expanduser('~/.reiteration'), config_file)
        config = yaml.safe_load(open(os.path.expanduser(config_file or '~/.reiteration/cache.yaml')))
    return config