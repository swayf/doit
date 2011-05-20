"""extra goodies to be used in dodo files"""

import os

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
    task.insert_action(save_executed)
    return values.get('run-once', False)


# debug helper
def set_trace(): # pragma: no cover
    """start debugger, make sure stdout shows pdb output.
    output is not restored.
    """
    import pdb
    import sys
    sys.stdout = sys.__stdout__
    pdb.Pdb().set_trace(sys._getframe().f_back) #pylint: disable=W0212

