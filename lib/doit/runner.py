"""Task runner."""

from doit import CatchedException, TaskFailed, SetupError, DependencyError
from doit.dependency import Dependency


class SetupManager(object):
    """Manage setup objects

    Setup object is any object that implements 'setup' and/or 'cleanup'
    @ivar _loaded (list): of loaded setup objects
    """

    def __init__(self):
        self._loaded = set()


    def load(self, setup_obj):
        """run setup from a setup_obj if it is not loaded yet"""
        if setup_obj in self._loaded:
            return

        try:
            self._loaded.add(setup_obj)
            if hasattr(setup_obj, 'setup'):
                setup_obj.setup()

        except (SystemExit, KeyboardInterrupt), exp: raise
        except Exception, exception:
            raise SetupError("ERROR on object setup", exception)


    def cleanup(self):
        """run cleanup for all loaded objects"""
        for setup_obj in self._loaded:
            if hasattr(setup_obj, 'cleanup'):
                try:
                    setup_obj.cleanup()
                # report error but keep result as successful.
                except Exception, e:
                    raise SetupError("ERROR on setup_obj cleanup", e)


# execution result.
SUCCESS = 0
FAILURE = 1
ERROR = 2

def run_tasks(dependencyFile, tasks, reporter, task_stdout=None,
              task_stderr=None, alwaysExecute=False, continue_=False):
    """This will actually run/execute the tasks.
    It will check file dependencies to decide if task should be executed
    and save info on successful runs.
    It also deals with output to stdout/stderr.

    @param dependencyFile: (string) file path of the db file
    @param tasks: (list) - L{Task} tasks to be executed
    @param reporter: reporter to be used. It can be a class or an object
    @param task_stdout: file like obj or None to capture
    @param task_stderr: file like obj or None to capture
    @param alwaysExecute: (bool) execute even if up-to-date
    @param continue_: (bool) execute all tasks even after a task failure
    """
    dependencyManager = Dependency(dependencyFile)
    setupManager = SetupManager()
    final_result = SUCCESS # we are optmistic

    for task in tasks:
        reporter.start_task(task)
        try:
            # check if task is up-to-date
            try:
                task_uptodate, task.dep_changed = dependencyManager.up_to_date(
                        task.name, task.file_dep, task.targets, task.run_once, task.result_dep)
            except Exception, exception:
                raise DependencyError("ERROR checking dependencies", exception)

            # if task id up-to-date skip it
            if not alwaysExecute and task_uptodate:
                reporter.skip_uptodate(task)
                continue

            # setup env
            for setup_obj in task.setup:
                setupManager.load(setup_obj)

            # finally execute it!
            reporter.execute_task(task)
            task.execute(task_stdout, task_stderr)

            # save execution successful
            if task.run_once:
                dependencyManager.save_run_once(task.name)
            dependencyManager.save_dependencies(task.name,task.file_dep)
            dependencyManager.save_resultdependencies(task.name,task.result_dep)
            dependencyManager.save_result(task.name, task.value)

            reporter.add_success(task)

        # in python 2.4 SystemExit and KeyboardInterrupt subclass
        # from Exception.
        # specially a problem when a fork from the main process
        # exit using sys.exit() instead of os._exit().
        except (SystemExit, KeyboardInterrupt), exp:
            raise

        # task error
        except CatchedException, exception:
            reporter.add_failure(task, exception)
            # only return FAILURE if no errors happened.
            if isinstance(exception, TaskFailed):
                final_result = FAILURE
                dependencyManager.remove_value(task.name)
            else:
                final_result = ERROR
            if not continue_:
                break


    ## done
    # flush update dependencies
    dependencyManager.close()
    # clean setup objects
    try:
        setupManager.cleanup()
    except SetupError, e:
        reporter.cleanup_error(e)

    # report final results
    reporter.complete_run()
    return final_result
