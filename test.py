from time import sleep

import unittest

from functioncache import functioncache, FileBackend, DictBackend, MemcacheBackend

@functioncache(backend=DictBackend())
def test_dict(x, y) :
    return x + y

@functioncache(backend=FileBackend())
def test_file(x, y) :
    return x - y

class FunctioncacheTest(unittest.TestCase) :
    def test_dict_cache(self) :
        self.counter = 0
        #@functioncache(backend=MemcacheBackend())
        @functioncache(backend=DictBackend())
        #@functioncache(backend=FileBackend())
        #@functioncache()
        def test(x, y) :
            self.counter += 1
            return x + y

        assert test(1, 2) == 3
        assert test(1, 2) == 3
        assert test(1, 2) == 3
        assert self.counter == 1

    def test_multicache_types(self) :
        assert test_dict(1, 2) == 3
        assert test_dict(1, 2) == 3
        assert test_dict(1, 2) == 3

        assert test_file(1, 2) == -1
        assert test_file(1, 2) == -1
        assert test_file(1, 2) == -1

        # this is a bit delicate since it could be effected by other
        # tests which use more backends.  This count should be the
        # total number of backend types used in this file
        import functioncache
        assert len(functioncache.OPEN_DBS) == 2

if __name__ == '__main__' :
    unittest.main()
