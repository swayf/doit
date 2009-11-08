import sys
import StringIO

from doit import reporter
from doit.task import Task
from doit import CatchedException
from doit.dependency import json #FIXME move json import to __init__.py

class BaseTestOutput(object):
    """base class for tests that use stdout"""
    def setUp(self):
        self.oldOut = sys.stdout
        sys.stdout = StringIO.StringIO()
        self.oldErr = sys.stderr
        sys.stderr = StringIO.StringIO()

    def tearDown(self):
        sys.stdout.close()
        sys.stdout = self.oldOut
        sys.stderr.close()
        sys.stderr = self.oldErr


class TestConsoleReporter(BaseTestOutput):
    def setUp(self):
        BaseTestOutput.setUp(self)
        self.rep = reporter.ConsoleReporter(True, True)
        self.my_task = Task("t_name", None)

    def test_startTask(self):
        self.rep.start_task(self.my_task)
        # no output on start task
        assert "" in sys.stdout.getvalue()

    def test_executeTask(self):
        self.rep.execute_task(self.my_task)
        assert "t_name" in sys.stdout.getvalue()

    def test_skipUptodate(self):
        self.rep.skip_uptodate(self.my_task)
        assert "---" in sys.stdout.getvalue()
        assert "t_name" in sys.stdout.getvalue()

    def test_skipIgnore(self):
        self.rep.skip_ignore(self.my_task)
        assert "!!!" in sys.stdout.getvalue()
        assert "t_name" in sys.stdout.getvalue()


    def test_cleanupError(self):
        exception = CatchedException("I got you")
        self.rep.cleanup_error(exception)
        assert "I got you" in sys.stderr.getvalue()

    def test_addFailure(self):
        try:
            raise Exception("original exception message here")
        except Exception,e:
            catched = CatchedException("catched exception there", e)
        self.rep.add_failure(self.my_task, catched)
        self.rep.complete_run()
        got = sys.stderr.getvalue()
        # description
        assert "Exception: original exception message here" in got, got
        # traceback
        assert """raise Exception("original exception message here")""" in got
        # catched message
        assert "catched exception there" in got


class TestExecutedOnlyReporter(BaseTestOutput):
    def setUp(self):
        BaseTestOutput.setUp(self)
        self.rep = reporter.ExecutedOnlyReporter(True, True)
        self.my_task = Task("t_name", None)

    def test_skipUptodate(self):
        self.rep.skip_uptodate(self.my_task)
        assert "" == sys.stdout.getvalue()

    def test_skipIgnore(self):
        self.rep.skip_ignore(self.my_task)
        assert "" == sys.stdout.getvalue()

    def test_executeGroupTask(self):
        self.rep.execute_task(self.my_task)
        assert "" == sys.stdout.getvalue()

    def test_executeTask(self):
        def do_nothing():pass
        t1 = Task("with_action",[(do_nothing,)])
        self.rep.execute_task(t1)
        assert "with_action" in sys.stdout.getvalue()



class TestTaskResult(object):
    def test(self):
        def sample():
            print "this is printed"
        t1 = Task("t1", [(sample,)])
        result = reporter.TaskResult(t1)
        result.start()
        t1.execute()
        result.set_result('success')
        got = result.to_dict()
        assert t1.name == got['name'], got
        assert 'success' == got['result'], got
        assert "this is printed\n" == got['out'], got
        assert "" == got['err'], got
        assert got['started']
        assert got['elapsed']


class TestJsonReporter(BaseTestOutput):
    def test(self):
        rep = reporter.JsonReporter()
        t1 = Task("t1", None)
        t2 = Task("t2", None)
        t3 = Task("t3", None)
        t4 = Task("t4", None)
        expected = {'t1':'fail', 't2':'up-to-date',
                    't3':'success', 't4':'ignore'}
        # t1 fail
        rep.start_task(t1)
        rep.execute_task(t1)
        rep.add_failure(t1, Exception('hi'))
        # t2 skipped
        rep.start_task(t2)
        rep.skip_uptodate(t2)
        # t3 success
        rep.start_task(t3)
        rep.execute_task(t3)
        rep.add_success(t3)
        # t4 ignore
        rep.start_task(t4)
        rep.skip_ignore(t4)

        rep.complete_run()
        got = json.loads(sys.stdout.getvalue())
        assert expected[got[0]['name']] == got[0]['result'], got
        assert expected[got[1]['name']] == got[1]['result'], got
        assert expected[got[2]['name']] == got[2]['result'], got
        assert expected[got[3]['name']] == got[3]['result'], got

        # just ignore this
        rep.cleanup_error(Exception('xx'))