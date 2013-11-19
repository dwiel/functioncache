"""
functioncache

functioncache is a decorator which saves the return value of functions even
after the interpreter dies. For example this is useful on functions that download
and parse webpages. All you need to do is specify how long
the return values should be cached (use seconds, like time.sleep).

USAGE:

    from functioncache import functioncache
    
    @functioncache(24 * 60 * 60)
    def time_consuming_function(args):
        # etc
    
    @functioncache(functioncache.YEAR)
    def another_function(args):
        # etc


NOTE: All arguments of the decorated function and the return value need to be
    picklable for this to work.

NOTE: The cache isn't automatically cleaned, it is only overwritten. If your
    function can receive many different arguments that rarely repeat, your
    cache may forever grow. One day I might add a feature that once in every
    100 calls scans the db for outdated stuff and erases.

NOTE: This is less useful on methods of a class because the instance (self)
    is cached, and if the instance isn't the same, the cache isn't used. This
    makes sense because class methods are affected by changes in whatever
    is attached to self.

Tested on python 2.7 and 3.1

License: BSD, do what you wish with this. Could be awesome to hear if you found
it useful and/or you have suggestions. ubershmekel at gmail


A trick to invalidate a single value:

    @functioncache.functioncache
    def somefunc(x, y, z):
        return x * y * z
        
    del somefunc._db[functioncache._args_key(somefunc, (1,2,3), {})]
    # or just iterate of somefunc._db (it's a shelve, like a dict) to find the right key.


"""


import collections as _collections
import datetime as _datetime
import functools as _functools
import inspect as _inspect
import os as _os
import cPickle as _pickle
import shelve as _shelve
import sys as _sys
import time as _time
import traceback as _traceback
import errno as _errno
import types as _types

_retval = _collections.namedtuple('_retval', 'timesig data')
_SRC_DIR = _os.path.dirname(_os.path.abspath(__file__))
_CACHE_ROOT=_os.path.expanduser("~/.functioncache")

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY
MONTH = 30 * DAY
YEAR = 365 * DAY
FOREVER = None

OPEN_DBS = dict()

def _mkdir_p(path) :
    try:
        _os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == _errno.EEXIST and _os.path.isdir(path):
            pass
        else: raise

def _get_cache_name(function):
    """
    returns a name for the module's cache db.
    """
    module_name = _inspect.getfile(function)
    cache_name = module_name
    
    # fix for '<string>' or '<stdin>' in exec or interpreter usage.
    cache_name = cache_name.replace('<', '_lt_')
    cache_name = cache_name.replace('>', '_gt_')
    
    cache_name += '.cache'
    cache_name = _CACHE_ROOT + _os.path.abspath(cache_name)
    cache_dir=_os.path.dirname(cache_name)
    if not _os.path.exists(cache_dir):
        _mkdir_p(cache_dir)
    return cache_name


def _log_error(error_str):
    try:
        error_log_fname = _os.path.join(_SRC_DIR, 'functioncache.err.log')
        if _os.path.isfile(error_log_fname):
            fhand = open(error_log_fname, 'a')
        else:
            fhand = open(error_log_fname, 'w')
        fhand.write('[%s] %s\r\n' % (_datetime.datetime.now().isoformat(), error_str))
        fhand.close()
    except Exception:
        pass

def _args_key(function, args, kwargs):
    arguments = (args, kwargs)
    # Check if you have a valid, cached answer, and return it.
    # Sadly this is python version dependant
    if _sys.version_info[0] == 2:
        arguments_pickle = _pickle.dumps(arguments)
    else:
        # NOTE: protocol=0 so it's ascii, this is crucial for py3k
        #       because shelve only works with proper strings.
        #       Otherwise, we'd get an exception because
        #       function.__name__ is str but dumps returns bytes.
        arguments_pickle = _pickle.dumps(arguments, protocol=0).decode('ascii')
        
    key = function.__name__ + arguments_pickle
    return key

class ShelveBackend(object) :
    """
    store cache data in a file based on the filename of the file which
    contains the function being cached.  One cache file can store multiple
    functions' data.
    """
    def setup(self, function) :
        self.shelve = _shelve.open(_get_cache_name(function))
    
    def __contains__(self, key) :
        return key in self.shelve
    
    def __getitem__(self, key) :
        return self.shelve[key]
    
    def __setitem__(self, key, value) :
        # NOTE: no need to _db.sync() because there was no mutation
        # NOTE: it's importatnt to do _db.sync() because otherwise the cache doesn't survive Ctrl-Break!
        self.shelve[key] = value
        self.shelve.sync()

import hashlib
class FileBackend(object) :
    """
    provide a backend to functioncache which stores each function argument
    combination in a different file.  This works around the problem caused
    by multiple python processes/threads trying to use the same file for
    caching.  This will still fail if the same function with the same arguments
    try to write simultaneously.  The ShelveBackend will fail often
    if any function in the same python file tries to write simultaneously.
    """
    def setup(self, function) :
        self.dir_name = _get_cache_name(function) + 'd'
        _mkdir_p(self.dir_name)

    def __contains__(self, key) :
        return _os.path.isfile(self._get_filename(key))
    
    def __getitem__(self, key) :
        return _pickle.load(open(self._get_filename(key)))
    
    def __setitem__(self, key, value) :
        # first-write wins semantics.  if someone else already cached this
        # value while we were off computing it, don't bother writing.  If we do
        # write, and the other process is still writing, we may corrupt the
        # file
        import portalocker
        
        try :
            file = open(self._get_filename(key), 'w')
            portalocker.Lock(file, portalocker.LOCK_EX)
            _pickle.dump(value, file)
        except portalocker.LockException, e :
            # someone else had the lock, thats ok, we don't have to
            # write the value if someone else already is
            pass
        except Exception, e :
            # delete the file in the event of an exception during saving
            # to protect from corrupted files causing problems later
            _os.remove(self._get_filename(key))
            raise
    
    def _get_filename(self, key) :
        # hash the key and use as a filename
        return self.dir_name + '/' + hashlib.sha512(key).hexdigest()

class DictBackend(dict) :
    """ cached values won't persist outside of this thread """
    def setup(self, function) :
        pass

class MemcacheBackend(object) :
    """ simple wrapper around memcache """
    def setup(self, function) :
        pass
    
    def __init__(self, mc=None) :
        if mc :
            self.mc = mc
        else :
            import memcache
            self.mc = memcache.Client(['127.0.0.1:11211'], debug=0)
    
    def __contains__(self, key) :
        return self[key] != None
    
    def __getitem__(self, key) :
        return self.mc.get(self._hash_key(key))
    
    def __setitem__(self, key, value) :
        if not self.mc.set(self._hash_key(key), value) :
            raise Exception("memcache set failed")
    
    def _hash_key(self, key) :
        # the key needs hashed to remove the invalid characters from the
        # pickled data and avoid problems with key length
        return hashlib.sha512(key).hexdigest()

class S3Backend(object) :
    """ wrapper around s3 - requires you to pass in an s3pool """

    def setup(self, function) :
        self.data_set = _get_cache_name(function)

    def __init__(self, s3pool=None) :
        if not s3pool :
            s3pool = create_s3pool()
        
        self.s3pool = s3pool

    def __contains__(self, key) :
        return bool(self.s3pool.list(self.data_set, key))

    def __getitem__(self, key) :
        return self.s3pool.get_contents_as_string(self.data_set, key)

    def __setitem__(self, key, value) :
        return self.s3pool.set_contents_from_string(self.data_set, key, value)
    

def functioncache(seconds_of_validity=None, fail_silently=True, backend=ShelveBackend()):
    '''
    functioncache is called and the decorator should be returned.
    '''
    # if a class is passed in, create an instance of that class as the backend
    if isinstance(backend, _types.ClassType) or isinstance(backend, type) :
        backend = backend()
    
    def functioncache_decorator(function):
        @_functools.wraps(function)
        def function_with_cache(*args, **kwargs):
            try:
                key = _args_key(function, args, kwargs)

                if key in function._db:
                    rv = function._db[key]
                    if seconds_of_validity is None or _time.time() - rv.timesig < seconds_of_validity:
                        return rv.data
            except :
                # in any case of failure, don't let functioncache break the program
                error_str = _traceback.format_exc()
                _log_error(error_str)
                if not fail_silently:
                    raise
            
            retval = function(*args, **kwargs)

            # store in cache
            try:
                function._db[key] = _retval(_time.time(), retval)
            except :
                # in any case of failure, don't let functioncache break the program
                error_str = _traceback.format_exc()
                _log_error(error_str)
                if not fail_silently:
                    raise
            
            return retval

        # make sure cache is loaded
        if not hasattr(function, '_db'):
            cache_name = (_get_cache_name(function), type(backend))
            if cache_name in OPEN_DBS:
                function._db = OPEN_DBS[cache_name]
            else:
                backend.setup(function)
                function._db = backend
                OPEN_DBS[cache_name] = function._db
            
            function_with_cache._db = function._db
            
        return function_with_cache

    if type(seconds_of_validity) == _types.FunctionType:
        # support for when people use '@functioncache.functioncache' instead of '@functioncache.functioncache()'
        func = seconds_of_validity
        return functioncache_decorator(func)
    
    return functioncache_decorator

def dictcache(seconds_of_validity=None, fail_silently=False) :
    return functioncache(seconds_of_validity, fail_silently, DictBackend())

def filecache(seconds_of_validity=None, fail_silently=False) :
    return functioncache(seconds_of_validity, fail_silently, FileBackend())

def shelvecache(seconds_of_validity=None, fail_silently=False) :
    return functioncache(seconds_of_validity, fail_silently, ShelveBackend())

def memcachecache(seconds_of_validity=None, fail_silently=False, mc=None) :
    return functioncache(
        seconds_of_validity, fail_silently, MemcacheBackend(mc)
    )

if _os.path.exists(_os.path.expanduser("~/.disable_functioncache")) :
    print 'disabled functioncache'
    def functioncache(*_, **__) :
        def nop_decorator(function) :
            return function
        return nop_decorator
