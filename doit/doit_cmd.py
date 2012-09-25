"""doit CLI (command line interface)"""

import os
import sys
import traceback

import doit
from .exceptions import InvalidDodoFile, InvalidCommand, InvalidTask
from .cmdparse import CmdParseError
from .cmd_base import Command
from .cmd_run import Run
from .cmd_clean import Clean
from .cmd_list import List
from .cmd_forget import Forget
from .cmd_ignore import Ignore
from .cmd_auto import Auto



HELP_TASK = """

Task Dictionary parameters
--------------------------

Tasks are defined by functions starting with the string ``task_``. It must return a dictionary describing the task with the following fields:

actions [required]:
  - type: Python-Task -> tuple (callable, `*args`, `**kwargs`)
  - type: Cmd-Task -> string or list of strings (each item is a different command). to be executed by shell.
  - type: Group-Task -> None.

basename:
  - type: string. if present use it as task name instead of taking name from python function

name [required for sub-task]:
  - type: string. sub-task identifier

file_dep:
  - type: list. items:
    * file (string) path relative to the dodo file

task_dep:
  - type: list. items:
    * task name (string)

targets:
  - type: list of strings
  - each item is file-path relative to the dodo file (accepts both files and folders)

uptodate:
  - type: list. items:
    * None - None values are just ignored
    * bool - False indicates task is not up-to-date
    * callable - returns bool or None. must take 2 positional parameters (task, values)

calc_dep:
  - type: list. items:
    * task name (string)

getargs:
  - type: dictionary
    * key: string with the name of the function parater (used in a python-action)
    * value: string on the format <task-name>.<variable-name>

setup:
 - type: list. items:
   * task name (string)

teardown:
 - type: (list) of actions (see above)

doc:
 - type: string -> the description text

clean:
 - type: (True bool) remove target files
 - type: (list) of actions (see above)

params:
 - type: (list) of dictionaries containing:
   - name [required] (string) parameter identifier
   - default [required] default value for parameter
   - short [optional] (string - 1 letter) short option string
   - long [optional] (string) long option string
   - type [optional] the option will be converted to this type

verbosity:
 - type: int
   -  0: capture (do not print) stdout/stderr from task.
   -  1: (default) capture stdout only.
   -  2: do not capture anything (print everything immediately).

title:
 - type: callable taking one parameter as argument (the task reference)
"""



class Help(Command):
    doc_purpose = "show help"
    doc_usage = ""
    doc_description = None

    @staticmethod
    def print_task_help():
        """print help for 'task' usage """
        print HELP_TASK

    def execute(self, params, args):
        """execute cmd 'help' """
        if len(args) == 1:
            if args[0] in params['sub']:
                print params['sub'][args[0]].help()
                return 0
            elif args[0] == 'task':
                self.print_task_help()
                return 0
        DoitMain.print_usage()
        return 0




DOIT_BUILTIN_CMDS = (Help(), Run(), List(), Clean(), Forget(), Ignore(), Auto())

class DoitMain(object):
    @staticmethod
    def print_version():
        """print doit version (includes path location)"""
        print ".".join([str(i) for i in doit.__version__])
        print "bin @", os.path.abspath(__file__)
        print "lib @", os.path.dirname(os.path.abspath(doit.__file__))

    @staticmethod
    def print_usage():
        """print doit "usage" (basic help) instructions"""
        # TODO cmd list should be automatically generated.
        print """
doit -- automation tool
http://python-doit.sourceforge.net/

Commands:
 doit [run]             run tasks
 doit clean             clean action / remove targets
 doit list              list tasks from dodo file
 doit forget            clear successful run status from DB
 doit ignore            ignore task (skip) on subsequent runs
 doit auto              automatically run doit when a dependency changes

 doit help              show help / reference
 doit help task         show help on task dictionary fields
 doit help <command>    show command usage
"""

def cmd_main(cmd_args):
    """entry point for all commands

    return codes:
      0: tasks executed successfully
      1: one or more tasks failed
      2: error while executing a task
      3: error before task execution starts,
         in this case the Reporter is not used.
         So be aware if you expect a different formatting (like JSON)
         from the Reporter.
    """

    # special parameters that dont run anything
    if cmd_args:
        if cmd_args[0] == "--version":
            DoitMain.print_version()
            return 0
        if cmd_args[0] == "--help":
            DoitMain.print_usage()
            return 0


    # all sub-commands
    sub_cmd = dict((cmd.name, cmd) for cmd in DOIT_BUILTIN_CMDS)

    # get cmdline variables from args
    doit.reset_vars()
    args_no_vars = []
    for arg in cmd_args:
        if (arg[0] != '-') and ('=' in arg):
            name, value = arg.split('=', 1)
            doit.set_var(name, value)
        else:
            args_no_vars.append(arg)


    # get specified sub-command or use default='run'
    if len(args_no_vars) == 0 or args_no_vars[0] not in sub_cmd.keys():
        command = 'run'
    else:
        command = args_no_vars.pop(0)


    # execute command
    try:
        return sub_cmd[command].parse_execute(args_no_vars, sub=sub_cmd)

    # dont show traceback for user errors.
    except (CmdParseError, InvalidDodoFile,
            InvalidCommand, InvalidTask), err:
        sys.stderr.write("ERROR: %s\n" % str(err))
        return 3

    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 3

