"""Manage (save/check) task dependency-on-files data."""

import os
import hashlib
import dumbdbm
import anydbm as ddbm

# uncomment imports below to run tests on all dbm backends...
#import dbhash as ddbm # (removed from python3)
#import dumbdbm as ddbm
#import dbm as ddbm
#import gdbm as ddbm

# note: to check which DBM backend is being used:
#       >>> anydbm._defaultmod

from .compat import json


USE_FILE_TIMESTAMP = True


def get_md5(input_data):
    """return md5 from string or unicode"""
    if isinstance(input_data, unicode):
        byte_data = input_data.encode("utf-8")
    else:
        byte_data = input_data
    return hashlib.md5(byte_data).hexdigest()

def md5sum(path):
    """Calculate the md5 sum from file content.

    @param path: (string) file path
    @return: (string) md5
    """
    file_data = open(path,'rb')
    result = get_md5(file_data.read())
    file_data.close()
    return result


def check_modified(file_path, file_stat, state):
    """check if file in file_path is modified from previous "state"
    @param file_path (string): file path
    @param file_stat: the value returned from os.stat(file_path)
    @param state (tuple), timestamp, size, md5
    @returns (bool):
    """
    if state is None:
        return True

    timestamp, size, file_md5 = state
    # 1 - if timestamp is not modified file is the same
    if USE_FILE_TIMESTAMP and file_stat.st_mtime == timestamp:
        return False
    # 2 - if size is different file is modified
    if file_stat.st_size != size:
        return True
    # 3 - check md5
    return file_md5 != md5sum(file_path)


class JsonDB(object):
    """Backend using a single text file with JSON content"""

    def __init__(self, name):
        """Open/create a DB file"""
        self.name = name
        if not os.path.exists(self.name):
            self._db = {}
        else:
            self._db = self._load()

    def _load(self):
        """load db content from file"""
        db_file = open(self.name, 'r')
        try:
            try:
                return json.load(db_file)
            except ValueError, error:
                # file contains corrupted json data
                msg = (error.args[0] +
                       "\nInvalid JSON data in %s\n" %
                       os.path.abspath(self.name) +
                       "To fix this problem, you can just remove the " +
                       "corrupted file, a new one will be generated.\n")
                error.args = (msg,)
                raise
        finally:
            db_file.close()

    def dump(self):
        """save DB content in file"""
        try:
            db_file = open(self.name, 'w')
            json.dump(self._db, db_file)
        finally:
            db_file.close()

    def set(self, task_id, dependency, value):
        """Store value in the DB."""
        if task_id not in self._db:
            self._db[task_id] = {}
        self._db[task_id][dependency] = value


    def get(self, task_id, dependency):
        """Get value stored in the DB.

        @return: (string) or (None) if entry not found
        """
        if task_id in self._db:
            return self._db[task_id].get(dependency, None)


    def in_(self, task_id):
        """@return bool if task_id is in DB"""
        return task_id in self._db


    def remove(self, task_id):
        """remove saved dependecies from DB for taskId"""
        if task_id in self._db:
            del self._db[task_id]

    def remove_all(self):
        """remove saved dependecies from DB for all tasks"""
        self._db = {}


class DbmDB(object):
    """Backend using a DBM file with individual values encoded in JSON

    On initialization all items are read from DBM file and loaded on _dbm.
    During execution whenever an item is read ('get' method) the json value
    is cached on _db. If a item is modified _db is update and the id is added
    to the 'dirty' set. Only on 'dump' all dirty items values are encoded
    in json into _dbm and the DBM file is saved.

    @ivar name: (str) file name/path
    @ivar _dbm: (dbm) items with json encoded values
    @ivar _db: (dict) items with python-dict as value
    @ivar dirty: (set) id of modified tasks
    """
    DBM_CONTENT_ERROR_MSG = 'db type could not be determined'

    def __init__(self, name):
        """Open/create a DB file"""
        self.name = name
        try:
            self._dbm = ddbm.open(self.name, 'c')
        except ddbm.error, exception:
            message = str(exception)
            if message == self.DBM_CONTENT_ERROR_MSG:
                # When a corrupted/old format database is found
                # suggest the user to just remove the file
                new_message = (
                    'Dependencies file in %(filename)s seems to use '
                    'an old format or is corrupted.\n'
                    'To fix the issue you can just remove the database file(s) '
                    'and a new one will be generated.'
                    % {'filename': repr(self.name)})
                raise exception.__class__, new_message
            else:
                # Re-raise any other exceptions
                raise

        self._db = {}
        self.dirty = set()

    def dump(self):
        """save/close DBM file"""
        for task_id in self.dirty:
            self._dbm[task_id] = json.dumps(self._db[task_id])
        self._dbm.close()

    def set(self, task_id, dependency, value):
        """Store value in the DB."""
        if task_id not in self._db:
            self._db[task_id] = {}
        self._db[task_id][dependency] = value
        self.dirty.add(task_id)

    def _in_dbm(self, key):
        """
        should be just::
          return key in self._dbm

         python3: when for get/set key is convert to bytes but not for 'in'
         fix #23 'in' operator not supported on DBM implementations on py2.6
        """
        return self._dbm.has_key(key.encode('utf-8'))


    def get(self, task_id, dependency):
        """Get value stored in the DB.

        @return: (string) or (None) if entry not found
        """
        # optimization, just try to get it without checking it exists
        if task_id in self._db:
            return self._db[task_id].get(dependency, None)
        else:
            try:
                task_data = self._dbm[task_id]
            except KeyError:
                return
            self._db[task_id] = json.loads(task_data.decode('utf-8'))
            return self._db[task_id].get(dependency, None)


    def in_(self, task_id):
        """@return bool if task_id is in DB"""
        return self._in_dbm(task_id) or task_id in self.dirty


    def remove(self, task_id):
        """remove saved dependecies from DB for taskId"""
        if task_id in self._db:
            del self._db[task_id]
        if self._in_dbm(task_id):
            del self._dbm[task_id]
        if task_id in self.dirty:
            self.dirty.remove(task_id)

    def remove_all(self):
        """remove saved dependecies from DB for all tasks"""
        self._db = {}
        # dumb dbm always opens file in update mode
        if isinstance(self._dbm, dumbdbm._Database): # pragma: no cover
            self._dbm._index = {}
            self._dbm.close()
        # gdbm can not be running on 2 instances on same thread
        # see https://bitbucket.org/schettino72/doit/issue/16/
        del self._dbm
        self._dbm = ddbm.open(self.name, 'n')
        self.dirty = set()



class DependencyBase(object):
    """Manage tasks dependencies (abstract class)

    Each dependency is a saved in "db". the "db" can have json or dbm
    format where there is a dictionary for every task. each task has a
    dictionary where key is a dependency (abs file path), and the value is the
    dependency signature.
    Apart from dependencies onther values are also saved on the task dictionary
     * 'result:', 'task:<task-name>', 'ignore:'
     * user(task) defined values are defined in '_values_:' sub-dict

    @ivar name: (string) filepath of the DB file
    @ivar _closed: (bool) DB was flushed to file
    """

    def __init__(self, backend):
        self._closed = False
        self.backend = backend
        self._set = self.backend.set
        self._get = self.backend.get
        self.remove = self.backend.remove
        self.remove_all = self.backend.remove_all
        self._in = self.backend.in_
        self.name = self.backend.name

    def close(self):
        """Write DB in file"""
        if not self._closed:
            self.backend.dump()
            self._closed = True


    ####### task specific

    def save_success(self, task):
        """save info after a task is successfuly executed"""
        # save task values
        self._set(task.name, "_values_:", task.values)

        # save task result md5
        if task.result:
            if isinstance(task.result, dict):
                self._set(task.name, "result:", task.result)
            else:
                self._set(task.name, "result:", get_md5(task.result))

        # file-dep
        for dep in task.file_dep:
            timestamp = os.path.getmtime(dep)
            # time optimization. if dep is already saved with current timestamp
            # skip calculating md5
            current = self._get(task.name, dep)
            if current and current[0] == timestamp:
                continue
            size = os.path.getsize(dep)
            self._set(task.name, dep, (timestamp, size, md5sum(dep)))


    def get_values(self, task_name):
        """get all saved values from a task
        @return dict
        """
        values = self._get(task_name, '_values_:')
        return values or {}

    def get_value(self, task_id, key_name):
        """get saved value from task
        @param task_id (str)
        @param key_name (str): key result dict of the value
        """
        if not self._in(task_id):
            # FIXME do not use generic exception
            raise Exception("taskid '%s' has no computed value!" % task_id)
        values = self.get_values(task_id)
        if key_name not in values:
            msg = "Invalid arg name. Task '%s' has no value for '%s'."
            raise Exception(msg % (task_id, key_name))
        return values[key_name]

    def remove_success(self, task):
        """remove saved info from task"""
        self.remove(task.name)

    def ignore(self, task):
        """mark task to be ignored"""
        self._set(task.name, 'ignore:', '1')

    def status_is_ignore(self, task):
        """check if task is marked to be ignored"""
        return self._get(task.name, "ignore:")

    # TODO add option to log this
    def get_status(self, task, tasks_dict):
        """Check if task is up to date. set task.dep_changed

        @param task: (Task)
        @param tasks_dict: (dict: Task) passed to objects used on uptodate
        @return: (str) one of up-to-date, run

        task.dep_changed (list-strings): file-dependencies that are not
        up-to-date if task not up-to-date because of a target, returned value
        will contain all file-dependencies reagrdless they are up-to-date
        or not.
        """
        task.dep_changed = []

        # check uptodate bool/callables
        checked_uptodate = False
        for utd, utd_args, utd_kwargs in task.uptodate:
            # if parameter is a callable
            if hasattr(utd, '__call__'):
                # FIXME control verbosity, check error messages
                # 1) prepare arguments
                args = [task, self.get_values(task.name)] + utd_args
                # 2) setup object with global info all tasks
                if isinstance(utd, UptodateCalculator):
                    utd.setup(self, tasks_dict)
                # 3) call it and get result
                uptodate_result = utd(*args, **utd_kwargs)
            # parameter is a value
            else:
                uptodate_result = utd

            # None means uptodate was not really calculated and should be
            # just ignored
            if uptodate_result is None:
                continue
            if uptodate_result:
                checked_uptodate = True
            else:
                return 'run'

        # no dependencies means it is never up to date.
        if not (task.file_dep or checked_uptodate):
            return 'run'

        # if target file is not there, task is not up to date
        for targ in task.targets:
            if not os.path.exists(targ):
                task.dep_changed = list(task.file_dep)
                return 'run'

        # check for modified file_dep
        changed = []
        status = 'up-to-date' # initial assumption
        for dep in tuple(task.file_dep):
            try:
                file_stat = os.stat(dep)
            except os.error:
                raise Exception("Dependent file '%s' does not exist." % dep)
            if check_modified(dep, file_stat, self._get(task.name, dep)):
                changed.append(dep)
                status = 'run'

        task.dep_changed = changed #FIXME create a separate function for this
        return status


class JsonDependency(DependencyBase):
    """Task dependency manager with JSON backend"""
    def __init__(self, name):
        DependencyBase.__init__(self, JsonDB(name))

class DbmDependency(DependencyBase):
    """Task dependency manager with DBM backend"""
    def __init__(self, name):
        DependencyBase.__init__(self, DbmDB(name))


class UptodateCalculator(object):
    """Base class for 'uptodate' that need access to all tasks
    """
    def __init__(self):
        self.get_val = None # Dependency._get
        self.tasks_dict = None # dict with all tasks

    def setup(self, dep_manager, tasks_dict):
        """@param"""
        self.get_val = dep_manager._get
        self.tasks_dict = tasks_dict




import platform
python_version = platform.python_version().split('.')
if python_version[0] == '2' and python_version[1] == '5': # pragma: no cover
    # use json by default on python2.5 because gdbm in python2.5 is broken
    Dependency = JsonDependency
else:
    Dependency = DbmDependency

