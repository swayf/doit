import os
from multiprocessing import Queue

import py.test

from doit.dependency import Dependency
from doit.task import Task
from doit.reporter import FakeReporter
from doit.main import TaskControl
from doit import runner

# dependencies file
TESTDB = "testdb"


# sample actions
def my_print(*args):
    pass
def _fail():
    return False
def _error():
    raise Exception("I am the exception.\n")
def _exit():
    raise SystemExit()


def pytest_funcarg__reporter(request):
    def remove_testdb(void):
        if os.path.exists(TESTDB):
            os.remove(TESTDB)
    def create_fake_reporter():
        remove_testdb(None)
        return FakeReporter()
    return request.cached_setup(
        setup=create_fake_reporter,
        teardown=remove_testdb,
        scope="function")


class TestRunner(object):
    def testInit(self, reporter):
        my_runner = runner.Runner(TESTDB, reporter)
        assert False == my_runner._stop_running
        assert runner.SUCCESS == my_runner.final_result


class TestRunner_SelectTask(object):
    def test_ok(self, reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )])
        my_runner = runner.Runner(TESTDB, reporter)
        assert True == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_DependencyError(self,reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )],
                  dependencies=["i_dont_exist"])
        my_runner = runner.Runner(TESTDB, reporter)
        assert False == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert ('fail', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_upToDate(self,reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )], dependencies=[__file__])
        my_runner = runner.Runner(TESTDB, reporter)
        my_runner.dependencyManager.save_success(t1)
        assert False == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert ('up-to-date', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_ignore(self,reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )])
        my_runner = runner.Runner(TESTDB, reporter)
        my_runner.dependencyManager.ignore(t1)
        assert False == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert ('ignore', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_alwaysExecute(self, reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )])
        my_runner = runner.Runner(TESTDB, reporter, always_execute=True)
        my_runner.dependencyManager.ignore(t1)
        assert True == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_noSetup_ok(self, reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )])
        my_runner = runner.Runner(TESTDB, reporter)
        assert True == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_withSetup(self, reporter):
        t1 = Task("taskX", [(my_print, ["out a"] )], setup=["taskY"])
        my_runner = runner.Runner(TESTDB, reporter)
        # defer execution
        assert False == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        assert not reporter.log
        # trying to select again
        assert True == my_runner.select_task(t1)
        assert not reporter.log


    def test_getargs_ok(self, reporter):
        def ok(): return {'x':1}
        def check_x(my_x): return my_x == 1
        t1 = Task('t1', [(ok,)])
        t2 = Task('t2', [(check_x,)], getargs={'my_x':'t1.x'})
        my_runner = runner.Runner(TESTDB, reporter)

        # execute task t1 to calculate value
        assert True == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        t1_result = my_runner.execute_task(t1)
        assert ('execute', t1) == reporter.log.pop(0)
        my_runner.process_task_result(t1, t1_result)
        assert ('success', t1) == reporter.log.pop(0)

        # t2.options are set on select_task
        assert {} == t2.options
        assert True == my_runner.select_task(t2)
        assert ('start', t2) == reporter.log.pop(0)
        assert not reporter.log
        assert {'my_x': 1} == t2.options

    def test_getargs_fail(self, reporter):
        # invalid getargs. Exception wil be raised and task will fail
        def check_x(my_x): return True
        t1 = Task('t1', [lambda :True])
        t2 = Task('t2', [(check_x,)], getargs={'my_x':'t1.x'})
        my_runner = runner.Runner(TESTDB, reporter)

        # execute task t1 to calculate value
        assert True == my_runner.select_task(t1)
        assert ('start', t1) == reporter.log.pop(0)
        t1_result = my_runner.execute_task(t1)
        assert ('execute', t1) == reporter.log.pop(0)
        my_runner.process_task_result(t1, t1_result)
        assert ('success', t1) == reporter.log.pop(0)

        # select_task t2 fails
        assert False == my_runner.select_task(t2)
        assert ('start', t2) == reporter.log.pop(0)
        assert ('fail', t2) == reporter.log.pop(0)
        assert not reporter.log


class TestTask_Teardown(object):
    def test_ok(self, reporter):
        touched = []
        def touch():
            touched.append(1)
        t1 = Task('t1', [], teardown=[(touch,)])
        my_runner = runner.Runner(TESTDB, reporter)
        my_runner.teardown_list = [t1]
        my_runner.teardown()
        assert 1 == len(touched)
        assert ('teardown', t1) == reporter.log.pop(0)
        assert not reporter.log

    def test_errors(self, reporter):
        def raise_something(x):
            raise Exception(x)
        t1 = Task('t1', [], teardown=[(raise_something,['t1 blow'])])
        t2 = Task('t2', [], teardown=[(raise_something,['t2 blow'])])
        my_runner = runner.Runner(TESTDB, reporter)
        my_runner.teardown_list = [t1, t2]
        my_runner.teardown()
        assert ('teardown', t1) == reporter.log.pop(0)
        assert ('cleanup_error',) == reporter.log.pop(0)
        assert ('teardown', t2) == reporter.log.pop(0)
        assert ('cleanup_error',) == reporter.log.pop(0)
        assert not reporter.log

def pytest_generate_tests(metafunc):
    if TestRunner_All == metafunc.cls:
        for RunnerClass in (runner.Runner, runner.MP_Runner):
            metafunc.addcall(id=RunnerClass.__name__,
                             funcargs=dict(RunnerClass=RunnerClass))
# TODO test action is picklable (closures are not)


def ok(): return "ok"
def ok2(): return "different"

#TODO unit-test individual methods: handle_task_error, ...
class TestRunner_All(object):

    def test_teardown(self, reporter, RunnerClass):
        t1 = Task('t1', [], teardown=[ok])
        t2 = Task('t2', [])
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl([t1, t2])
        tc.process(None)
        assert [] == my_runner.teardown_list
        my_runner.run_tasks(tc)
        my_runner.finish()
        assert ('teardown', t1) == reporter.log[-1]

    # testing whole process/API
    def test_success(self, reporter, RunnerClass):
        tasks = [Task("taskX", [(my_print, ["out a"] )] ),
                 Task("taskY", [(my_print, ["out a"] )] )]
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.SUCCESS == my_runner.finish()
        assert ('start', tasks[0]) == reporter.log.pop(0), reporter.log
        assert ('execute', tasks[0]) == reporter.log.pop(0)
        assert ('success', tasks[0]) == reporter.log.pop(0)
        assert ('start', tasks[1]) == reporter.log.pop(0)
        assert ('execute', tasks[1]) == reporter.log.pop(0)
        assert ('success', tasks[1]) == reporter.log.pop(0)

    # whenever a task fails remaining task are not executed
    def test_failureOutput(self, reporter, RunnerClass):
        tasks = [Task("taskX", [_fail]),
                 Task("taskY", [_fail])]
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.FAILURE == my_runner.finish()
        assert ('start', tasks[0]) == reporter.log.pop(0)
        assert ('execute', tasks[0]) == reporter.log.pop(0)
        assert ('fail', tasks[0]) == reporter.log.pop(0)
        # second task is not executed
        assert 0 == len(reporter.log)


    def test_error(self, reporter, RunnerClass):
        tasks = [Task("taskX", [_error]),
                 Task("taskY", [_error])]
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.ERROR == my_runner.finish()
        assert ('start', tasks[0]) == reporter.log.pop(0)
        assert ('execute', tasks[0]) == reporter.log.pop(0)
        assert ('fail', tasks[0]) == reporter.log.pop(0)
        # second task is not executed
        assert 0 == len(reporter.log)


    # when successful dependencies are updated
    def test_updateDependencies(self, reporter, RunnerClass):
        filePath = os.path.join(os.path.dirname(__file__),"data/dependency1")
        ff = open(filePath,"a")
        ff.write("xxx")
        ff.close()
        dependencies = [filePath]

        filePath = os.path.join(os.path.dirname(__file__),"data/target")
        ff = open(filePath,"a")
        ff.write("xxx")
        ff.close()
        targets = [filePath]

        tasks = [Task("taskX", [my_print], dependencies, targets)]
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.SUCCESS == my_runner.finish()
        d = Dependency(TESTDB)
        # there is only one dependency. targets md5 are not saved.
        assert 1 == len(d._db)

    # when successful and run_once is updated
    def test_successRunOnce(self, reporter, RunnerClass):
        tasks = [Task("taskX", [my_print], [True], [])]
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.SUCCESS == my_runner.finish()
        d = Dependency(TESTDB)
        assert 1 == len(d._db)

    def test_resultDependency(self, reporter, RunnerClass):
        t1 = Task("t1", [(ok,)])
        t2 = Task("t2", [(ok,)], ['?t1'])
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl([t1, t2])
        tc.process(None)
        my_runner.run_tasks(tc)
        my_runner.finish()
        assert ('start', t1) == reporter.log.pop(0)
        assert ('execute', t1) == reporter.log.pop(0)
        assert ('success', t1) == reporter.log.pop(0)
        assert ('start', t2) == reporter.log.pop(0)
        assert ('execute', t2) == reporter.log.pop(0)
        assert ('success', t2) == reporter.log.pop(0)

        # again
        t1 = Task("t1", [(ok,)])
        t2 = Task("t2", [(ok,)], ['?t1'])
        my_runner2 = RunnerClass(TESTDB, reporter)
        tc2 = TaskControl([t1, t2])
        tc2.process(None)
        my_runner2.run_tasks(tc2)
        my_runner2.finish()
        assert ('start', t1) == reporter.log.pop(0)
        assert ('execute', t1) == reporter.log.pop(0)
        assert ('success', t1) == reporter.log.pop(0)
        assert ('start', t2) == reporter.log.pop(0)
        assert ('up-to-date', t2) == reporter.log.pop(0)

        # change t1, t2 executed again
        t1B = Task("t1", [(ok2,)])
        t2 = Task("t2", [(ok,)], ['?t1'])
        my_runner3 = RunnerClass(TESTDB, reporter)
        tc3 = TaskControl([t1B, t2])
        tc3.process(None)
        my_runner3.run_tasks(tc3)
        my_runner3.finish()
        assert ('start', t1B) == reporter.log.pop(0)
        assert ('execute', t1B) == reporter.log.pop(0)
        assert ('success', t1B) == reporter.log.pop(0)
        assert ('start', t2) == reporter.log.pop(0)
        assert ('execute', t2) == reporter.log.pop(0)
        assert ('success', t2) == reporter.log.pop(0)


    def test_continue(self, reporter, RunnerClass):
        tasks = [Task("task1", [(_fail,)] ),
                 Task("task2", [(_error,)] ),
                 Task("task3", [(ok,)])]
        my_runner = RunnerClass(TESTDB, reporter, continue_=True)
        tc = TaskControl(tasks)
        tc.process(None)
        my_runner.run_tasks(tc)
        assert runner.ERROR == my_runner.finish()
        assert ('start', tasks[0]) == reporter.log.pop(0)
        assert ('execute', tasks[0]) == reporter.log.pop(0)
        assert ('fail', tasks[0]) == reporter.log.pop(0)
        assert ('start', tasks[1]) == reporter.log.pop(0)
        assert ('execute', tasks[1]) == reporter.log.pop(0)
        assert ('fail', tasks[1]) == reporter.log.pop(0)
        assert ('start', tasks[2]) == reporter.log.pop(0)
        assert ('execute', tasks[2]) == reporter.log.pop(0)
        assert ('success', tasks[2]) == reporter.log.pop(0)
        assert 0 == len(reporter.log)


    # SystemExit runner should not interfere with SystemExit
    def testSystemExitRaises(self, reporter, RunnerClass):
        t1 = Task("x", [_exit])
        my_runner = RunnerClass(TESTDB, reporter)
        tc = TaskControl([t1])
        tc.process(None)
        py.test.raises(SystemExit, my_runner.run_tasks, tc)


class TestMP_Reporter(object):
    class MyRunner(object):
        def __init__(self):
            self.result_q = Queue()

    def testReporterMethod(self, reporter):
        fake_runner = self.MyRunner()
        mp_reporter = runner.MP_Runner.MP_Reporter(fake_runner, reporter)
        my_task = Task("task x", [])
        mp_reporter.add_success(my_task)
        got = fake_runner.result_q.get(True, 1)
        assert {'name': "task x", "reporter": 'add_success'} == got

    def testNonReporterMethod(self, reporter):
        fake_runner = self.MyRunner()
        mp_reporter = runner.MP_Runner.MP_Reporter(fake_runner, reporter)
        assert hasattr(mp_reporter, 'add_success')
        assert not hasattr(mp_reporter, 'no_existent_method')


class TestMP_Runner_get_next_task(object):
    # simple normal case
    def test_run_task(self, reporter):
        t1 = Task('t1', [])
        t2 = Task('t2', [])
        tc = TaskControl([t1, t2])
        tc.process(None)
        run = runner.MP_Runner(TESTDB, reporter)
        run.set_tasks(tc)
        assert t1 == run.get_next_task()
        assert t2 == run.get_next_task()
        assert None == run.get_next_task()

    def test_stop_running(self, reporter):
        t1 = Task('t1', [])
        t2 = Task('t2', [])
        tc = TaskControl([t1, t2])
        tc.process(None)
        run = runner.MP_Runner(TESTDB, reporter)
        run.set_tasks(tc)
        assert t1 == run.get_next_task()
        run._stop_running = True
        assert None == run.get_next_task()

    def test_waiting(self, reporter):
        t1 = Task('t1', [])
        t2a = Task('t2A', [], dependencies=(':t1',))
        t2b = Task('t2B', [], setup=('t1',))
        t3 = Task('t3', [], setup=('t2B',))
        tc = TaskControl([t1, t2a, t2b, t3])
        tc.process(None)
        run = runner.MP_Runner(TESTDB, reporter)
        run.set_tasks(tc)

        # first task ok
        assert t1 == run.get_next_task()

        # hold until t1 finishes
        assert 0 == run.free_proc
        assert isinstance(run.get_next_task(), runner.Hold)
        assert {'t1':['t2A', 't2B'], 't2B': ['t3']} == run.waiting
        assert 1 == run.free_proc

        # ready for t2x
        assert [] == run.ready_queue
        run.process_task_result(t1, None)
        assert ['t2A', 't2B'] == run.ready_queue
        assert {'t2B': ['t3']} == run.waiting

        # t2
        assert t2a == run.get_next_task()
        assert t2b == run.get_next_task()

        # t3
        assert isinstance(run.get_next_task(), runner.Hold)
        run.process_task_result(t2b, None)
        assert ['t3'] == run.ready_queue
        assert {} == run.waiting
        assert t3 == run.get_next_task()
        assert None == run.get_next_task()

# test cyclic dependency on MP
