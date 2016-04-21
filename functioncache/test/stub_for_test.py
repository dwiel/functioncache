
import time
from functioncache import dictcache


@dictcache(30)
def the_time():
    return time.time()
