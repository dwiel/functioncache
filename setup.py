try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


VERSION = '0.94'

SETUP_DICT = dict(
    name='functioncache',
    packages=['functioncache'],
    install_requires=['portalocker', 'decorator'],
    test_requires=['portalocker', 'decorator'],
    version=VERSION,
    author='zdwiel',
    author_email='zdwiel@gmail.com',
    url='https://github.com/dwiel/functioncache',
    description='Persistent caching decorator',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
  )

setup(**SETUP_DICT)
