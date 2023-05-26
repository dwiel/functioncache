from __future__ import print_function

import inspect
import unittest
import imp
import time
import random
import os

import functioncache
import tempfile

_CACHE_ROOT = "/tmp/.functioncache"

print("Using temporary _CACHE_ROOT = ", _CACHE_ROOT)
functioncache._CACHE_ROOT = _CACHE_ROOT


def erase_all_cache_files():
    shelve_suffixes = ('.cache', '.cache.bak', '.cache.dir', '.cache.dat')
    # os.listdir doesn't accept an empty string but dirname returns ''
    here = os.path.dirname(__file__) or '.'
    fname_list = os.listdir(here)

    for fname in fname_list:
        fpath = os.path.join(here, fname)
        # NOTE: test that path still exists because chained tests sometimes don't
        #       immediately erase things.
        if fname.endswith(shelve_suffixes) and os.path.exists(fpath):
            os.remove(fpath)

    import shutil
    shutil.rmtree(_CACHE_ROOT, ignore_errors=True)


# NOTE: this comes so early so that the NotInnerClass's @functioncache
# isn't erased from the disk
erase_all_cache_files()


class TestFunctioncache(unittest.TestCase):

    #@classmethod
    # def setUpClass(self):
    #    erase_all_cache_files()

    #@classmethod
    # def tearDownClass(self):
    #    erase_all_cache_files()

    def test_returns(self):
        # make sure the thing works
        @functioncache.functioncache(30)
        def donothing(x):
            return x

        params = [1, 'a', 'asdfa', set([1, 2, 3])]
        for item in params:
            self.assertEqual(donothing(item), item)

    def test_speeds(self):
        DELAY = 0.5

        @functioncache.functioncache(60)
        def waiter(x):
            time.sleep(DELAY)
            return x

        start = time.time()
        self.assertEqual(waiter(123), 123)
        self.assertEqual(waiter(123), 123)
        self.assertEqual(waiter(123), 123)
        self.assertEqual(waiter(123), 123)
        finish = time.time()

        # ran it 4 times but it should run faster than DELAY * 4
        self.assertLess(finish - start, (DELAY * 2))

    def test_invalidates(self):
        wait = 0.1
        items = [1337, 69]

        @functioncache.functioncache(wait)
        def popper():
            return items.pop()

        first = popper()
        # I would wait just for 'wait' exactly but time.time() isn't accurate
        # enough.
        time.sleep(wait * 1.1)
        second = popper()

        self.assertNotEqual(first, second)

    def test_interpreter_usage(self):
        '''
        This test is good for exec or interpreter usage of functioncache.

        inspect.getfile(function) returned a bad filename for these cases.

        e.g. old exception:
        IOError: [Errno 22] Invalid argument: '<string>.cache.dat'
        '''
        d = {}
        exec(
            '''from functioncache import functioncache\n@functioncache(60)\ndef function(x): return x''',
            d,
            d)
        first = d['function'](13)
        second = d['function'](13)
        self.assertEqual(first, second)

    def test_error_handling(self):

        temp = functioncache._log_error
        try:
            passed_test = [False]

            def mock_logger(*args, **kwargs):
                passed_test[0] = True

            functioncache._log_error = mock_logger

            def popper():
                return 'arbitrary obj here'

            # put anything in _db that you know will break functioncache
            popper._db = 123

            popper = functioncache.functioncache(
                0.1, fail_silently=True)(popper)

            first = popper()

            self.assertTrue(passed_test[0])
        finally:
            functioncache._log_error = temp

    # TODO: maybe make class methods work somehow, problem is methods rely on instance
    #       members so I'd have to serialize the class maybe. A bit complex.
    def AAA_test_class_methods(self):
        # won't work because class A isn't picklable
        class A:

            def __init__(self):
                self.number = 1

            @functioncache.functioncache(5.0)
            def donothing(self, x):
                self.number += x
                return self.number

        instance = NotInnerClass()
        first = instance.donothing(1)

        second = instance.donothing(1)
        self.assertEqual(first, second)

    def test_ignore_instance(self):
        class HashServer:

            def __init__(self, salt):
                self.salt = salt

            @functioncache.functioncache(23, ignore_instance=True)
            def get_hash(self, s):
                import hmac
                import hashlib

                h = hmac.new(self.salt.encode(), digestmod=hashlib.md5)
                for i in range(23 * 23):  # make the cache worthwile :)
                    h.update(s.encode())
                return h.hexdigest()

        hs1 = HashServer('salt')
        hs2 = HashServer('salt')
        self.assertEqual(hs1.get_hash('puppy'), hs2.get_hash('puppy'))
        hp = HashServer('pepper')  # you SHOULDN'T do this "in real life"
        # we expect a wrong answer here :)
        self.assertEqual(hs1.get_hash('puppy'), hp.get_hash('puppy'))

    def test_instance(self):
        class HashServer:

            def __init__(self, ret):
                self.ret = ret

            @functioncache.functioncache(23, ignore_instance=False)
            def get_ret(self):
                return self.ret

        hs1 = HashServer(1)
        hs2 = HashServer(2)
        self.assertEqual(hs1.get_ret(), 1)
        self.assertEqual(hs2.get_ret(), 2)

    def test_ignore_instance_no_args(self):
        class HashServer:

            def __init__(self, ret):
                self.ret = ret

            @functioncache.functioncache(23, ignore_instance=True)
            def get_ret(self):
                return self.ret

        hs1 = HashServer(1)
        hs2 = HashServer(2)
        self.assertEqual(hs1.get_ret(), 1)
        self.assertEqual(hs2.get_ret(), 1)

    def test_skipcache(self):
        broken = True  # simulate server down

        @functioncache.functioncache(42)
        def shaky_query(q):
            if broken:
                raise functioncache.SkipCache(
                    'Server is broken. Returning fallback result for "{0}"'.format(
                        q),  # Error message for log
                    'Error in query "{0}"'.format(q))  # return value for the caller
            # Server is up. Return the result we got
            return 'Result for query "{0}" is 42'.format(q)

        self.assertEqual(
            shaky_query('What time is love?'),
            'Error in query "What time is love?"')
        broken = False  # Server is back up. Now we can get the real answer. Let's hope we didn't cache the error
        self.assertEqual(
            shaky_query('What time is love?'),
            'Result for query "What time is love?" is 42')

    def test_inspect(self):
        @functioncache.dictcache
        def foo(x, y, z=None):
            return x, y, z

        spec = inspect.getfullargspec(foo)
        assert spec.args == ['x', 'y', 'z']
        assert spec.defaults == (None,)


class NotInnerClass:

    def __init__(self):
        self.number = 1

    @functioncache.functioncache(5.0, backend=functioncache.FileBackend())
    def donothing(self, x):
        self.number += x
        return self.number


if __name__ == '__main__':
    unittest.main()
    erase_all_cache_files()
