import os
import sys, StringIO

import nose.tools

from doit.task import create_task
from doit.task import InvalidTask, CmdTask, GroupTask
from doit.main import load_task_generators
from doit.main import generate_tasks
from doit.main import InvalidCommand, Main, cmd_list, cmd_run
from doit.main import InvalidDodoFile

class TestLoadTaskGenerators(object):

    def testAbsolutePath(self):
        fileName = os.path.abspath(__file__+"/../loader_sample.py")
        expected = ["xxx1","yyy2"]
        task_list = load_task_generators(fileName)
        assert expected == [t.name for t in task_list]

    def testRelativePath(self):
        # test relative import but test should still work from any path
        # so change cwd.
        os.chdir(os.path.abspath(__file__+"/../.."))
        fileName = "tests/loader_sample.py"
        expected = ["xxx1","yyy2"]
        task_list = load_task_generators(fileName)
        assert expected == [t.name for t in task_list]


class TestGenerateTasks(object):

    def testDict(self):
        tasks = generate_tasks("dict",{'action':'xpto 14'})
        assert isinstance(tasks[0],CmdTask)

    # name field is only for subtasks.
    def testInvalidNameField(self):
        nose.tools.assert_raises(InvalidTask, generate_tasks,"dict",
                                 {'action':'xpto 14','name':'bla bla'})

    def testDictMissingFieldAction(self):
        nose.tools.assert_raises(InvalidTask, generate_tasks,
                                 "dict",{'acTion':'xpto 14'})

    def testAction(self):
        tasks = generate_tasks("dict",'xpto 14')
        assert isinstance(tasks[0],CmdTask)


    def testGenerator(self):
        def f_xpto():
            for i in range(3):
                yield {'name':str(i), 'action' :"xpto -%d"%i}
        tasks = generate_tasks("xpto", f_xpto())
        assert isinstance(tasks[0], GroupTask)
        assert 4 == len(tasks)
        assert "xpto:0" == tasks[1].name

    def testGeneratorDoesntReturnDict(self):
        def f_xpto():
            for i in range(3):
                yield "xpto -%d"%i
        nose.tools.assert_raises(InvalidTask, generate_tasks,"xpto",
                                 f_xpto())

    def testGeneratorDictMissingName(self):
        def f_xpto():
            for i in range(3):
                yield {'action' :"xpto -%d"%i}
        nose.tools.assert_raises(InvalidTask, generate_tasks,"xpto",
                                 f_xpto())

    def testGeneratorDictMissingAction(self):
        def f_xpto():
            for i in range(3):
                yield {'name':str(i)}
        nose.tools.assert_raises(InvalidTask, generate_tasks,"xpto",
                                 f_xpto())


    def testDictFieldTypo(self):
        dict_ = {'action':'xpto 14','typo_here':['xxx']}
        nose.tools.assert_raises(InvalidTask, generate_tasks, "dict", dict_)



###################
class TestAddTask(object):

    def testadd_task(self):
        t1 = GroupTask("taskX", None)
        t2 = GroupTask("taskY", None)
        m = Main([t1, t2])
        assert 2 == len(m.tasks)

    # 2 tasks can not have the same name
    def testadd_taskSameName(self):
        t1 = GroupTask("taskX", None)
        t2 = GroupTask("taskX", None)
        nose.tools.assert_raises(InvalidDodoFile, Main, [t1, t2])

    def test_addInvalidTask(self):
        nose.tools.assert_raises(InvalidTask, Main, [666])


class TestOrderTasks(object):
    # same task is not added twice
    def testAddJustOnce(self):
        baseTask = create_task("taskX","xpto 14 7",[],[])
        m = Main([baseTask])
        result = m._order_tasks(["taskX"]*2)
        assert 1 == len(result)

    def testDetectCyclicReference(self):
        baseTask1 = create_task("taskX",None,[":taskY"],[])
        baseTask2 = create_task("taskY",None,[":taskX"],[])
        m = Main([baseTask1, baseTask2])
        nose.tools.assert_raises(InvalidDodoFile, m._order_tasks,
                                 ["taskX", "taskY"])



# FIXME: this are more like system tests.
# i must create a dodo file to test the processing part, but i should not.

# Main class needs to be split up. the load
# expected values from sample_main.py
TASKS = ['string','python','dictionary','dependency','generator','func_args',
         'taskdependency','targetdependency','mygroup']
ALLTASKS = ['string','python','dictionary','dependency','generator',
            'generator:test_runner.py','generator:test_util.py','func_args',
            'taskdependency','targetdependency','mygroup']
TESTDBM = "testdbm"
DODO_FILE = os.path.abspath(__file__+"/../sample_main.py")


class TestCmdList(object):

    def setUp(self):
        #setup stdout
        self.oldOut = sys.stdout
        sys.stdout = StringIO.StringIO()
        self.task_list = load_task_generators(DODO_FILE)

    def tearDown(self):
        #teardown stdout
        sys.stdout.close()
        sys.stdout = self.oldOut

    def testListTasks(self):
        cmd_list(self.task_list, False)
        assert TASKS == sys.stdout.getvalue().split('\n')[1:-3]

    def testListAllTasks(self):
        cmd_list(self.task_list, True)
        assert ALLTASKS == sys.stdout.getvalue().split('\n')[1:-3], sys.stdout.getvalue()




class TestMain(object):
    def setUp(self):
        #setup stdout
        self.oldOut = sys.stdout
        sys.stdout = StringIO.StringIO()
        self.task_list = load_task_generators(DODO_FILE)

    def tearDown(self):
        if os.path.exists(TESTDBM):
            os.remove(TESTDBM)
        #teardown stdout
        sys.stdout.close()
        sys.stdout = self.oldOut


    def testProcessRun(self):
        cmd_run(TESTDBM, self.task_list)
        assert [
            "string => Cmd: python sample_process.py sss",
            "python => Python: function do_nothing",
            "dictionary => Cmd: python sample_process.py ddd",
            "dependency => Python: function do_nothing",
            "generator:test_runner.py => Cmd: python sample_process.py test_runner.py",
            "generator:test_util.py => Cmd: python sample_process.py test_util.py",
            "generator => Group: ",
            "func_args => Python: function funcX",
            "taskdependency => Python: function do_nothing",
            "targetdependency => Python: function do_nothing",
            "mygroup => Group: :dictionary, :string"] == \
            sys.stdout.getvalue().split("\n")[:-1], repr(sys.stdout.getvalue())


    def testFilter(self):
        cmd_run(TESTDBM, self.task_list, filter_=["dictionary","string"])
        assert ["dictionary => Cmd: python sample_process.py ddd",
                "string => Cmd: python sample_process.py sss",] == \
                sys.stdout.getvalue().split("\n")[:-1]

    def testFilterSubtask(self):
        cmd_run(TESTDBM, self.task_list, filter_=["generator:test_util.py"])
        expect = ("generator:test_util.py => " +
                  "Cmd: python sample_process.py test_util.py")
        assert [expect,] == sys.stdout.getvalue().split("\n")[:-1]

    def testFilterTarget(self):
        cmd_run(TESTDBM, self.task_list, filter_=["test_runner.py"])
        assert ["dictionary => Cmd: python sample_process.py ddd",] == \
                sys.stdout.getvalue().split("\n")[:-1]


    # filter a non-existent task raises an error
    def testFilterWrongName(self):
        nose.tools.assert_raises(InvalidCommand,cmd_run,TESTDBM,
                      self.task_list, filter_=["XdictooonaryX","string"])


    def testGroup(self):
        cmd_run(TESTDBM, self.task_list, filter_=["mygroup"])
        assert ["dictionary => Cmd: python sample_process.py ddd",
                "string => Cmd: python sample_process.py sss",
                "mygroup => Group: :dictionary, :string"] == \
                sys.stdout.getvalue().split("\n")[:-1], sys.stdout.getvalue()


    def testTaskDependency(self):
        cmd_run(TESTDBM, self.task_list, filter_=["taskdependency"])
        assert ["generator:test_runner.py => Cmd: python sample_process.py test_runner.py",
                "generator:test_util.py => Cmd: python sample_process.py test_util.py",
                "generator => Group: ",
                "taskdependency => Python: function do_nothing"] == \
                sys.stdout.getvalue().split("\n")[:-1], sys.stdout.getvalue()


    def testTargetDependency(self):
        cmd_run(TESTDBM, self.task_list, filter_=["targetdependency"])
        assert ["dictionary => Cmd: python sample_process.py ddd",
                "targetdependency => Python: function do_nothing"] == \
                sys.stdout.getvalue().split("\n")[:-1]

    def testUserErrorTaskDependency(self):
        nose.tools.assert_raises(InvalidTask, cmd_run, TESTDBM,
                                 [GroupTask('wrong', None,[":typo"])])
