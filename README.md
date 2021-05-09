# devcache
A configurable decorator allows methods to return persistently stored data from a cache instead of a normal call.

The use case is to speed up development by caching data from long-running methods   

### Installation
``pip install devcache``


**Situation**

You're working on a project that syncs data from a Database to a CRM.  


```Python
def get_crm_data():  # Takes multiple minutes
    ...

def get_db_data():  # Takes multiple minutes
    ...    

def compare_and_report():
    crm_data = get_crm_data()
    db_data = get_db_data()
    ...
    diff = ...
    result = save_data(diff)
    ...
    send_report(report)
        
def save_data(data):  # Takes more than a minute
    ...
```

As you are trying to improve ``compare_and_report`` it takes 5 minutes for everytime you run.

A possible solution would be to use ``devcache``, like so:

#### Decorate appropriate methods 
```Python
@devcache(group='crm')
def get_crm_data():  # Takes multiple minutes
     ...

@devcache(group='db')
def get_db_data():  # Takes multiple minutes
    ...    
    
@devcache(group='save')
def save_data(data):  # Takes more than a minute
    ...
```



#### Create a config at ~/.devcache/devcache.yaml
```yaml

props:
    1:
        group: crm
        use_cache: true
    2:
        group: db
        use_cache: true
    3:
        group: save
        use_cache: true

```

Now the methods will pull data from the cache as ``use_cache`` is ``true``.  If a change was required to any saved data set the `use_cache` to ``false`` and data will be generated and stored fresh in the cache.

Now using the cache each testing iteration takes seconds instead of minutes.

### Other useful configuration

```yaml
refresh: true  # refresh true will ignore use_cache and refresh all cached data 
enabled: false # will disable everything and will not save new values to cache
props:
    1:
        group: crm
        use_cache: false
    2:
        group: db
        use_cache: true
    3:
        group: save
        use_cache: true
    -1:  # first props match is used.  
         # ordering is by the key (ie -1, 1 ,2 ,3)   
         # 'group' is optional
        pattern: '.*sfdc.*' # matches fully qualified name of the method.  
                            # this pattern would match everything in a module called sfdc
        use_cache: true
        enabled: true # Can turn off props with enabled.  Will allow for other props to potentially match 

```

### Other devcache args

```Python
# devcache defaults to not take into account the args
@devcache(group='crm', key_args=('a', ))
def my_method(a, b, c):  # Will cache result using only arg 'a' value as part of the key 
    ...        

@devcache(group='crm', ignore_key_args=('c', ))
def another_method(a, b, c):  # Will cache result using arg 'a', 'b' value as part of the key ignoring 'c' 
    ...        

@devcache(config_file='../alternate.yaml')
def method3(a, b, c):  # specify another configuration 
    ...        


```

### Important Warning

This project is only useful to speed up development and is a security risk.

Best practice would be to not include ``devcache`` in project requirements for production and only installing it locally.

Creating project specific decorator will allow for functionality to work in the desired env and not break the other.

For example:
```Python
def cacher(config_file=None, group=None, key_args=None, ignore_key_args=None):
    def noop_decorator(func):
        return func  # pass through

    try:
        from devcache import devcache
        return devcache(config_file=config_file, group=group, key_args=key_args, ignore_key_args=ignore_key_args)
    except:
        return noop_decorator
```

Using ``@cacher`` decorator would have use a pass through decorator for prod but use ``devcache`` where it's installed.
