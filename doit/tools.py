"""extra goodies to be used in dodo files"""

import os
import time as time_module
import datetime
import hashlib
import operator
import subprocess

from . import exceptions
from .dependency import UptodateCalculator
from .action import CmdAction, PythonAction


# action
def create_folder(dir_path):
    """create a folder in the given path if it doesnt exist yet."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return True


# title
def title_with_actions(task):
    """return task name task actions"""
    if task.actions:
        title = "\n\t".join([unicode(action) for action in task.actions])
    # A task that contains no actions at all
    # is used as group task
    else:
        title = "Group: %s" % ", ".join(task.task_dep)
    return "%s => %s"% (task.name, title)



# uptodate
def run_once(task, values):
    """execute task just once
    used when user manually manages a dependency
    """
    def save_executed():
        return {'run-once': True}
    task.value_savers.append(save_executed)
    return values.get('run-once', False)



# uptodate
class result_dep(UptodateCalculator):
    """check if result of the given task was modified
    """
    def __init__(self, dep_task_name):
        self.dep_name = dep_task_name
        self.result_name = '_result:%s' % self.dep_name

    def configure_task(self, task):
        """to be called by doit when create the task"""
        # result_dep creates an implicit task_dep
        task.task_dep.append(self.dep_name)

    def _result_single(self):
        """get result from a single task"""
        return self.get_val(self.dep_name, 'result:')

    def _result_group(self, dep_task):
        """get result from a group task
        the result is the combination of results of all sub-tasks
        """
        prefix = dep_task.name + ":"
        sub_tasks = {}
        for sub in dep_task.task_dep:
            if sub.startswith(prefix):
                sub_tasks[sub] = self.get_val(sub, 'result:')
        return sub_tasks

    def __call__(self, task, values):
        """return True if result is the same as last run"""
        dep_task = self.tasks_dict[self.dep_name]
        if not dep_task.has_subtask:
            dep_result = self._result_single()
        else:
            dep_result = self._result_group(dep_task)
        task.value_savers.append(lambda: {self.result_name: dep_result})

        last_success = values.get(self.result_name)
        if last_success is None:
            return False
        return (last_success == dep_result)



# uptodate
class config_changed(object):
    """check if passed config was modified
    @var config (str) or (dict)
    """
    def __init__(self, config):
        self.config = config
        self.config_digest = None

    def _calc_digest(self):
        if isinstance(self.config, basestring):
            return self.config
        elif isinstance(self.config, dict):
            data = ''
            for key in sorted(self.config):
                data += key + repr(self.config[key])
            if isinstance(data, unicode): # pragma: no cover # python3
                byte_data = data.encode("utf-8")
            else:
                byte_data = data
            return hashlib.md5(byte_data).hexdigest()
        else:
            raise Exception(('Invalid type of config_changed parameter got %s' +
                             ', must be string or dict') % (type(self.config),))

    def configure_task(self, task):
        task.value_savers.append(lambda: {'_config_changed':self.config_digest})

    def __call__(self, task, values):
        """return True if confing values are UNCHANGED"""
        self.config_digest = self._calc_digest()
        last_success = values.get('_config_changed')
        if last_success is None:
            return False
        return (last_success == self.config_digest)



# uptodate
class timeout(object):
    """add timeout to task

    @param timeout_limit: (datetime.timedelta, int) in seconds

    if the time elapsed since last time task was executed is bigger than
    the "timeout" time the task is NOT up-to-date
    """

    def __init__(self, timeout_limit):
        if isinstance(timeout_limit, datetime.timedelta):
            self.limit_sec = ((timeout_limit.days * 24 * 3600) +
                              timeout_limit.seconds)
        elif isinstance(timeout_limit, int):
            self.limit_sec = timeout_limit
        else:
            msg = "timeout should be datetime.timedelta or int got %r "
            raise Exception(msg % timeout_limit)

    def __call__(self, task, values):
        def save_now():
            return {'success-time': time_module.time()}
        task.value_savers.append(save_now)
        last_success = values.get('success-time', None)
        if last_success is None:
            return False
        return (time_module.time() - last_success) < self.limit_sec



# uptodate
class check_timestamp_unchanged(object):
    """check if timestamp of a given file/dir is unchanged since last run.

    The C{cmp_op} parameter can be used to customize when timestamps are
    considered unchanged, e.g. you could pass L{operator.ge} to also consider
    e.g. files reverted to an older copy as unchanged; or pass a custom
    function to completely customize what unchanged means.

    If the specified file does not exist, an exception will be raised.  Note
    that if the file C{fn} is a target of another task you should probably add
    C{task_dep} on that task to ensure the file is created before checking it.
    """
    def __init__(self, file_name, time='mtime', cmp_op=operator.eq):
        """initialize the callable

        @param fn: (str) path to file/directory to check
        @param time: (str) which timestamp field to check, can be one of
                     (atime, access, ctime, status, mtime, modify)
        @param cmp_op: (callable) takes two parameters (prev_time, current_time)
                   should return True if the timestamp is considered unchanged

        @raises ValueError: if invalid C{time} value is passed
        """
        if time in ('atime', 'access'):
            self._timeattr = 'st_atime'
        elif time in ('ctime', 'status'):
            self._timeattr = 'st_ctime'
        elif time in ('mtime', 'modify'):
            self._timeattr = 'st_mtime'
        else:
            raise ValueError('time can be one of: atime, access, ctime, '
                             'status, mtime, modify (got: %r)' % time)
        self._file_name = file_name
        self._cmp_op = cmp_op
        self._key = '.'.join([self._file_name, self._timeattr])

    def _get_time(self):
        return getattr(os.stat(self._file_name), self._timeattr)

    def __call__(self, task, values):
        """register action that saves the timestamp and check current timestamp

        @raises OSError: if cannot stat C{self._file_name} file
                         (e.g. doesn't exist)
        """
        def save_now():
            return {self._key: self._get_time()}
        task.value_savers.append(save_now)

        prev_time = values.get(self._key)
        if prev_time is None: # this is first run
            return False
        current_time = self._get_time()
        return self._cmp_op(prev_time, current_time)


# action
class InteractiveAction(CmdAction):
    """Action to handle Interactive shell process:
        * the output is never captured
        * it is always successful (return code is not used)
        * "swallow" KeyboardInterrupt
    """
    def execute(self, out=None, err=None):
        action = self.expand_action()
        process = subprocess.Popen(action, shell=True)
        try:
            process.wait()
        except KeyboardInterrupt:
            pass # normal way to stop interactive process


# action
class PythonInteractiveAction(PythonAction):
    """Action to handle Interactive python:
        * the output is never captured
        * it is always successful (return code is not used)
          unless a exeception is raised
    """
    def execute(self, out=None, err=None):
        kwargs = self._prepare_kwargs()
        try:
            self.py_callable(*self.args, **kwargs)
        except Exception, exception:
            return exceptions.TaskError("PythonAction Error", exception)


# debug helper
def set_trace(): # pragma: no cover
    """start debugger, make sure stdout shows pdb output.
    output is not restored.
    """
    import pdb
    import sys
    debugger = pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__)
    debugger.set_trace(sys._getframe().f_back) #pylint: disable=W0212

