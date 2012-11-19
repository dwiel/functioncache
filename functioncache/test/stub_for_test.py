
import time
from functioncache import functioncache

@functioncache(30)
def the_time():
    return time.time()
