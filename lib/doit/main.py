"""doit command line program."""

import os
import sys
import inspect

from doit.util import isgenerator, OrderedDict
from doit.task import InvalidTask, GroupTask, create_task
from doit.runner import Runner


class InvalidCommand(Exception):
    """Invalid command line argument."""
    pass

class InvalidDodoFile(Exception):
    """Invalid dodo file"""
    pass

# TASK_STRING: (string) prefix used to identify python function
# that are task generators in a dodo file.
TASK_STRING = "task_"
# TASK_ATTRS: sequence of know attributes(keys) of a task dict.
TASK_ATTRS = ('name','action','dependencies','targets','args','kwargs')

def load_task_generators(dodoFile):
    """Loads a python file and extracts its task generator functions.

    The python file is a called "dodo" file.

    @param dodoFile: (string) path to file containing the tasks
    @return (tupple) (name, function reference)
    """
    ## load module dodo file and set environment
    base_path, file_name = os.path.split(os.path.abspath(dodoFile))
    # make sure dir is on sys.path so we can import it
    sys.path.insert(0, base_path)
    # file specified on dodo file are relative to itself.
    os.chdir(base_path)
    # get module containing the tasks
    dodo_module = __import__(os.path.splitext(file_name)[0])

    # get functions defined in the module and select the task generators
    # a task generator function name starts with the string TASK_STRING
    funcs = []
    prefix_len = len(TASK_STRING)
    # get all functions defined in the module
    for name,ref in inspect.getmembers(dodo_module, inspect.isfunction):
        # ignore functions that are not a task (by its name)
        if not name.startswith(TASK_STRING):
            continue
        # get line number where function is defined
        line = inspect.getsourcelines(ref)[1]
        # add to list task generator functions
        # remove TASK_STRING prefix from name
        funcs.append((name[prefix_len:],ref,line))
    # sort by the order functions were defined (line number)
    funcs.sort(key=lambda obj:obj[2])
    return [(name,ref) for name,ref,line in funcs]


def _dict_to_task(task_dict):
    """Create a task instance from dictionary.

    The dictionary has the same format as returned by task-generators
    from dodo files.

    @param task_dict: (dict) task representation as a dict.
    @raise L{InvalidTask}:
    """
    # FIXME: check this in another place
    # user friendly. dont go ahead with invalid input.
    for key in task_dict.keys():
        if key not in TASK_ATTRS:
            raise InvalidTask("Task %s contain invalid field: %s"%
                              (task_dict['name'],key))

    # check required fields
    if 'action' not in task_dict:
        raise InvalidTask("Task %s must contain field action. %s"%
                          (task_dict['name'],task_dict))

    return create_task(task_dict.get('name'),
                       task_dict.get('action'),
                       task_dict.get('dependencies',[]),
                       task_dict.get('targets',[]),
                       args=task_dict.get('args',[]),
                       kwargs=task_dict.get('kwargs',{}))

def order_tasks(all_, to_add):
    # put tasks in an order so that dependencies are executed before.
    # make sure a task is added only once. detected cyclic dependencies.
    ADDING, ADDED = 0, 1
    status = {}
    task_in_order = []

    def add_task(task):
        if task.name in status:
            # check task was alaready added
            if status[task.name] == ADDED:
                return

            # detect cyclic/recursive dependencies
            if status[task.name] == ADDING:
                msg = "Cyclic/recursive dependencies for task %s"
                raise InvalidDodoFile(msg % task)

        status[task.name] = ADDING

        # add dependencies first
        for dependency in task.task_dep:
            add_task(all_[dependency])

        # add itself
        task_in_order.append(task)
        status[task.name] = ADDED

    for task in to_add:
        add_task(task)
    return task_in_order



def generate_tasks(name, gen_result):
    """Create tasks from a task generator.

    @param name: (string) name of taskgen function
    @param gen_result: value returned by a task generator function
    @return: (tuple) task,list of subtasks
    """
    # task described as a dictionary
    if isinstance(gen_result,dict):
        if 'name' in gen_result:
            raise InvalidTask("Task %s. Only subtasks use field name."%name)

        gen_result['name'] = name
        return [_dict_to_task(gen_result)]

    # a generator
    if isgenerator(gen_result):
        tasks = []
        # the generator return subtasks as dictionaries .
        for task_dict in gen_result:
            # check valid input
            if not isinstance(task_dict, dict):
                raise InvalidTask("Task %s must yield dictionaries"% name)

            if 'name' not in task_dict:
                raise InvalidTask("Task %s must contain field name. %s"%
                                  (name,task_dict))
            # name is task.subtask
            task_dict['name'] = "%s:%s"% (name,task_dict.get('name'))
            sub_task = _dict_to_task(task_dict)
            sub_task.isSubtask = True
            tasks.append(sub_task)

        # create task. depends on subtasks
        gtask = GroupTask(name, None)
        gtask.task_dep = [task.name for task in tasks]
        tasks.append(gtask)
        return tasks

    # if not a dictionary nor a generator. "task" is the action itself.
    return [_dict_to_task({'name':name,'action':gen_result})]


def get_tasks(taskgen):
    """get tasks from list of task generators

    @param taskgen: (tupple) (name, function reference)
    @return orderedDict of BaseTask's
    """
    tasks = OrderedDict()
    # for each task generator
    for name, ref in taskgen:
        generated = generate_tasks(name, ref())
        for sub in generated:
            tasks[sub.name] = sub
    return tasks



class Main(object):
    """doit - load dodo file and execute tasks.

    @ivar dependencyFile: (string) file path of the dbm file.
    @ivar verbosity: (bool) verbosity level. @see L{Runner}

    @ivar list: (int) 0 dont list, run;
                      1 list task generators (do not run if listing);
                      2 list all tasks (do not run if listing);
    @ivar filter: (sequence of strings) selection of tasks to execute

    @ivar taskgen: (tupple) (name, function reference)

    @ivar tasks: (OrderedDict) Key: task name ([taskgen.]name)
                               Value: L{BaseTask} instance
    @ivar targets: (dict) Key: fileName
                          Value: L{BaseTask} instance
    """

    def __init__(self, dodoFile, dependencyFile,
                 list_=False, verbosity=0, alwaysExecute=False, filter_=None):

        ## intialize cmd line options
        self.dependencyFile = dependencyFile
        self.list = list_
        self.verbosity = verbosity
        self.alwaysExecute = alwaysExecute
        self.filter = filter_
        self.targets = {}
        self.taskgen = load_task_generators(dodoFile)
        self.tasks = get_tasks(self.taskgen)

    def _list_tasks(self, printSubtasks):
        """List task generators, in the order they were defined.

        @param printSubtasks: (bool) print subtasks
        """
        # this function is called when after the constructor,
        # and before task-dependencies and targets are processed
        # so task_dep contains only subtaks
        print "==== Tasks ===="
        for items in self.taskgen:
            generator = items[0]
            print generator
            if printSubtasks:
                for subtask in self.tasks[generator].task_dep:
                    if self.tasks[subtask].isSubtask:
                        print subtask

        print "="*25,"\n"


    def _filter_tasks(self):
        """Select tasks specified by filter.

        filter can specify tasks to be execute by task name or target.
        """
        # FIXME we just need a list of strings.
        selectedTaskgen = OrderedDict()
        for filter_ in self.filter:
            # by task name
            if filter_ in self.tasks.iterkeys():
                selectedTaskgen[filter_] = self.tasks[filter_]
            # by target
            elif filter_ in self.targets:
                selectedTaskgen[filter_] = self.targets[filter_]
            else:
                print self.targets
                raise InvalidCommand('"%s" is not a task/target.'% filter_)
        return selectedTaskgen




    def process(self):
        """Execute sub-comannd"""
        if self.list:
            return self.cmd_list()
        return self.run()

    def cmd_list(self):
        self._list_tasks(bool(self.list==2))
        return 0


    def run(self):
        """Execute tasks."""
        # check task-dependencies exist.
        for task in self.tasks.itervalues():
            for dep in task.task_dep:
                if dep not in self.tasks:
                    msg = "%s. Task dependency '%s' does not exist."
                    raise InvalidTask(msg% (task.name,dep))

        # get target dependecies on other tasks based on file dependency on
        # a target.
        # 1) create a dictionary associating every target->task. where the task
        # builds that target.
        for task in self.tasks.itervalues():
            for target in task.targets:
                self.targets[target] = task
        # 2) now go through all dependencies and check if they are target from
        # another task.
        for task in self.tasks.itervalues():
            for dep in task.file_dep:
                if (dep in self.targets and
                    self.targets[dep] not in task.task_dep):
                    task.task_dep.append(self.targets[dep].name)

        # if no filter is defined execute all tasks
        # in the order they were defined.
        selectedTask = None
        if not self.filter:
            selectedTask = self.tasks
        # execute only tasks in the filter in the order specified by filter
        else:
            selectedTask = self._filter_tasks()

        # create a Runner instance and ...
        runner = Runner(self.dependencyFile, self.verbosity, self.alwaysExecute)

        # add to runner tasks from every selected task
        taskorder = order_tasks(self.tasks, selectedTask.itervalues())
        for task in taskorder:
            runner.add_task(task)

        return runner.run()

