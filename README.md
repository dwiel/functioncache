# functioncache

functioncache is a decorator which saves the return value of functions even
after the interpreter dies. For example this is useful on functions that
download and parse webpages. All you need to do is specify how long the return
values should be cached (use seconds, like time.sleep).

## USAGE

```python
    from functioncache import functioncache

    @functioncache(24 * 60 * 60)
    def time_consuming_function(args):
        # etc

    @functioncache(functioncache.YEAR)
    def another_function(args):
        # etc
```

## USAGE FOR *INSTANCE AGNOSTIC* CLASS METHODS

Normally, you wouldn't want to cache class method results, because they may be
affected by changes to the state of the object (self).

*If you know what you're doing* and are sure that a class method would not be
affected by the object's state (for example - object is a proxy to a remote
service), you'll need to make sure the first argument (self) doesn't get cached.

In that case, you should use the `ignore_instance=True` keyword:

```python
    class db:
        @functioncache(functioncache.HOUR,ignore_instance=True)
        def query(...):
           ...
```

## THE SkipCache EXCEPTION

Sometimes something goes wrong (e.g. communication with a server times out), and
your function wants to return a "fail gracefully" fallback value, but you don't
want it cached. The SkipCache exception lets you do just that.  instead of
doing:
```python
  return some_fallback_value
```
you do:

```python
  raise SkipCache,"Server timeout",some_fallback_value
```

The caller of your function will get the value, but it won't get cached.
The error text ("Server timeout") will appear in functioncache's log.

Example:

```python
        try:
            user['avatar'] = self.twister.dhtget(username,'avatar','s')[0]['p']['v'] # yes. it's a "real life" example :)
        except: # Probably a temporary network glitch. Better not cache
            user['avatar'] = None # Client will show the default avatar
            raise SkipCache("couldn't get avatar for @{0}, not caching".format(username),user)
        return user
```

## NOTES

- All arguments of the decorated function and the return value need to be
  picklable for this to work.

- The cache isn't automatically cleaned, it is only overwritten. If your
  function can receive many different arguments that rarely repeat, your cache
  may forever grow. One day I might add a feature that once in every 100 calls
  scans the db for outdated stuff and erases.

Tested on python 2.7 and 3.1
(`ignore_instance` tested on python 2.7 and it rocks)


A trick to invalidate a single value:

```python
    @functioncache.functioncache
    def somefunc(x, y, z):
        return x * y * z

    del somefunc._db[functioncache._args_key(somefunc, (1,2,3), {})]
    # or just iterate of somefunc._db (it's a shelve, like a dict) to find the right key.
```

## LICENSE

License: BSD, do what you wish with this. Could be awesome to hear if you found
it useful and/or you have suggestions. ubershmekel at gmail

