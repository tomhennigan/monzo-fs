# coding=utf8

"""Diazed is a bottle inspired framework for writing FUSE file systems.

Diazed refers to D-type fuse cartridges which are commonly known as "bottle
fuses". https://en.wikipedia.org/wiki/IEC_60269#D-system_.28DIAZED.29

The framework works by users annotating functions to handle specific paths.
Paths are converted to regular expressions to match requests coming from the
OS, and groups are defined as <name>. If a path is matched then the groups are
passed through to the function as postional arguments. Rules are matched in
order, so if you had a function decorated with @readlink('/<foo>') and
say @readlink('/<bar>') it would not be possible to reach the second function
because it would be shadowed by the first.

Handler functions can return primative types (e.g. a directory can be
represented as a list of strings) or they can return diazed.Dir or diaezd.File
instances.

  Typical usage example:

  import fuse
  from diazed import fs, readlink, readdir

  @readdir('/')
  def list_root():
      return ['example.txt', 'foo.txt', 'bar.txt']

  @readlink('/example.txt')
  def read_example():
      return 'Hello, world!'

  @readlink('/<file>')
  def read_file(file):
      # This method will not match example.txt because read_example was
      # registered first.
      return 'You are reading %s.' % file

  fuse.FUSE(fs, '/tmp/myfs', foreground=True, direct_io=True)
"""

import collections
import errno
import re
import stat

import fuse


class Dir:
    """Represents a directory containing a list of nodes."""

    def __init__(self, contents, **attrs):
        """Construct a Dir instance.

        :param contents: The iterable contents of the directory.
        :param attrs: Additional attributes for this dir.
        """
        self.contents = list(contents)
        self.attrs = dict(st_mode=(stat.S_IFDIR | 0o555))
        for key, value in attrs.iteritems():
            self.attrs[key] = value

    def __iter__(self):
        return iter(self.contents)


class File:
    """Represents a file with byte contents."""

    def __init__(self, contents):
        """Constructs a File instance.

        :param contents: The contents of the file, which will become bytes.
        """

        self.contents = bytes(contents)
        self.attrs = dict(st_mode=(stat.S_IFREG | 0o444),
                          st_size=len(self.contents))

def _resolve_fs(_fs):
    """Resolves a specific file system, or returns the global one.

    :param _fs: A specific file system to use, or None.
    :returns: An _DiazedFileSystem instance.
    """
    if _fs:
        return _fs
    else:
        global fs
        return fs


def readlink(path, _fs=None):
    """Registers a function that reads a 'file' with the given fs.

    :param path: The path to match (e.g. "/<file>").
    :param _fs: An optional _DiazedFileSystem instance (mostly for testing).
    :returns: A decorator that will register the function with fs for path.
    """
    fs = _resolve_fs(_fs)
    return _get_decorator(fs, operations=['readlink'], paths=[path])


def readdir(path, _fs=None):
    """Decorates a function that lists a 'directory'.

    :param path: The path to match (e.g. "/<file>").
    :param _fs: An optional _DiazedFileSystem instance (mostly for testing).
    :returns: A decorator that will register the function with fs for path.
    """
    fs = _resolve_fs(_fs)
    return _get_decorator(fs, operations=['readdir'], paths=[path])


def mixed(operations, paths, _fs=None):
    """Decorates a function that supports multiple types of action.

    :param operations: The list of operations (e.g. ["readlink"]).
    :param paths: The paths to match (e.g. ["/<file>", "/<file>.txt"]).
    :param _fs: An optional _DiazedFileSystem instance (mostly for testing).
    :returns: A decorator that will register the function with fs for path.
    """
    fs = _resolve_fs(_fs)
    return _get_decorator(fs, operations=operations, paths=paths)


def _get_decorator(fs, operations, paths):
    """Decorator to wrap a function that returns the contents of a path.

    :param paths: the set of paths to handle.
    :return: a File object, bytes or something that will be turned into bytes.
    """
    def _decorator(fn):
        # Register the function as a handler for all the paths + operations.
        for path in paths:
            for operation in operations:
                fs.on(operation, path, _curry(fn, _ensure_obj))
        return fn
    return _decorator


def _ensure_obj(x):
    """Converts 'primative' types to diazed objects (e.g. list -> Dir).

    :param x: The object to cast or pass through.
    :returns: An instance of Dir or File based on the type of x.
    """
    t = type(x)
    if t in (Dir, File):
        return x
    elif t in (list, tuple, set):
        return Dir(x)
    else:
        return File(x)


def _curry(*fns):
    """Returns a function that curries the given functions together.

        >>> a = lambda v: 'a("%s")' % v
        >>> b = lambda v: 'b(%s)' % v
        >>> f = _curry(a, b)
        >>> f("something")
        b(a("something"))

    :param fns: A list of functions to curry.
    :returns: A callable that curries the given functions.
    """
    def __curry(*args, **kwargs):
        ret = fns[0](*args, **kwargs)
        for fn in fns[1:]:
            ret = fn(ret)
        return ret
    return __curry


class _UnableToRouteException(Exception):
    """Thrown when an action is unable to route for the given path."""
    pass


class _DiazedFileSystem(fuse.LoggingMixIn, fuse.Operations):
    """A FUSE file system that forwards syscalls to decorated functions."""

    def __init__(self):
        self.routes = collections.defaultdict(lambda: [])
        self.fd = 0

    def on(self, operation, route, callback):
        """Registers a handler for a specific operation/route pair.

        :param operation: The str name of the operation (e.g. "readlink").
        :param route: The str route to handle (e.g. "/<file>.txt").
        :param callback: A callback to call when route/operation is matched.
        """
        route = '^' + re.sub('<[^>]*>', '([^/]*)', route) + '$'
        self.routes[operation].append((re.compile(route), callback))

    def route(self, operation, path, **fuseargs):
        """Handles a specific routing of a path (e.g. "/foo/bar") to a handler.

        :param operation: The str name of the operation (e.g. "readlink").
        :param path: The str path to handle (e.g. "/foo/bar").
        :param fuseargs: A set of fuse kwargs.
        :throws: _UnableToRouteException if unable to handle path + operation.
        :returns: The value returned by the callback for the given path + op.
        """
        for route, callback in self.routes[operation]:
            match = route.match(path)
            if match is not None:
                # TODO(tomhennigan) Find a way to optionally pass **fuseargs
                #                   without requiring them to be passed. 
                return callback(*match.groups())
        raise _UnableToRouteException('Unable to handle %s' % path)

    def _create_fuse_args(self, **kwargs):
        """Creates a kwargs dict with keys prepended with "_fuse_".

        :param kwargs: The kwargs to copy.
        :returns: A copy of kwargs with keys prefixed with "_fuse_".
        """
        return {'_fuse_' + k: v for k, v in kwargs.iteritems()}

    def _raise_readonlyfs(self):
        raise fuse.FuseOSError(errno.EROFS)

    """File system methods."""

    def readdir(self, path, fh):
        kwargs = self._create_fuse_args(fh=fh)
        return ['.', '..'] + self.route('readdir', path, **kwargs).contents

    def readlink(self, path):
        return self.route('readlink', path).contents

    def getattr(self, path, fh=None):
        kwargs = self._create_fuse_args(fh=fh)

        try:
            return self.route('readdir', path, **kwargs).attrs
        except _UnableToRouteException:
            pass

        try:
            return self.route('readlink', path).attrs
        except _UnableToRouteException:
            pass

        raise fuse.FuseOSError(errno.ENOENT)

    def getxattr(self, path, name, position=0):
        kwargs = self._create_fuse_args(name=name, position=position)
        try:
            return self.route('getxattr', path, **kwargs)
        except _UnableToRouteException:
            pass

        return ''

    def listxattr(self, path):
        try:
            return self.route('listxattr', path)
        except _UnableToRouteException:
            pass

        return []

    def open(self, path, flags):
        kwargs = self._create_fuse_args(flags=flags)
        try:
            self.route('open', path, **kwargs)
        except _UnableToRouteException:
            pass

        self.fd += 1
        return self.fd

    def read(self, path, size, offset, fh):
        kwargs = self._create_fuse_args(size=size, offset=offset, fh=fh)
        try:
            return self.route('read', path, **kwargs).contents
        except _UnableToRouteException:
            pass

        # Fallback to reading the whole file and slicing ourselves.
        return self.readlink(path)[offset:offset + size]

    def statfs(self, path):
        return {}

    def create(self, path, mode):
        self._raise_readonlyfs()

    def write(self, path, data, offset, fh):
        self._raise_readonlyfs()

    def truncate(self, path, length, fh=None):
        self._raise_readonlyfs()

    def unlink(self, path):
        self._raise_readonlyfs()

    def chmod(self, path, mode):
        self._raise_readonlyfs()

    def chown(self, path, uid, gid):
        self._raise_readonlyfs()

    def mkdir(self, path, mode):
        self._raise_readonlyfs()

    def removexattr(self, path, name):
        self._raise_readonlyfs()

    def rename(self, old, new):
        self._raise_readonlyfs()

    def rmdir(self, path):
        self._raise_readonlyfs()

    def setxattr(self, path, name, value, options, position=0):
        self._raise_readonlyfs()

    def symlink(self, target, source):
        self._raise_readonlyfs()

    def utimens(self, path, times=None):
        self._raise_readonlyfs()


# A global file system instance that is used by default.
# TODO(tomhennigan) Should we create this lazily?
fs = _DiazedFileSystem()
