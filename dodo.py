"""dodo file. test + management stuff"""

import glob
import os

import pytest

from doit.tools import create_folder

DOIT_CONFIG = {'default_tasks': ['checker', 'ut']}

CODE_FILES = glob.glob("doit/*.py")
TEST_FILES = glob.glob("tests/test_*.py")
TESTING_FILES = glob.glob("tests/*.py")
PY_FILES = CODE_FILES + TESTING_FILES


def task_checker():
    """run pyflakes on all project files"""
    for module in PY_FILES:
        yield {'actions': ["pyflakes %(dependencies)s"],
               'name':module,
               'file_dep':(module,),
               'title': (lambda task: task.name)}

def run_test(test):
    return not bool(pytest.main(test))
def task_ut():
    """run unit-tests"""
    for test in TEST_FILES:
        yield {'name': test,
               'actions': [(run_test, (test,))],
               'file_dep': PY_FILES,
               'verbosity': 0}


################## coverage tasks

def task_coverage():
    """show coverage for all modules including tests"""
    return {'actions':
                ["coverage run --parallel-mode `which py.test` ",
                 "coverage combine",
                 ("coverage report --show-missing %s" %
                  " ".join(CODE_FILES + TEST_FILES))
                 ],
            'verbosity': 2}


def task_coverage_code():
    """show coverage for all modules (exclude tests)"""
    return {'actions':
                ["coverage run --parallel-mode `which py.test` ",
                 "coverage combine",
                 "coverage report --show-missing %s" % " ".join(CODE_FILES)],
            'verbosity': 2}


def task_coverage_module():
    """show coverage for individual modules"""
    to_strip = len('tests/test_')
    for test in TEST_FILES:
        source = "doit/" + test[to_strip:]
        yield {'name': test,
               'actions':
                   ["coverage run --parallel-mode `which py.test` -v %s" % test,
                    "coverage combine",
                    "coverage report --show-missing %s %s" % (source, test)],
               'verbosity': 2}


############# python3

# distribute => setup.py test together with use_2to3 doesnt work hence this
def task_test3():
    """run unitests on python3"""
    this_folder = os.path.dirname(os.path.abspath(__file__))
    test_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "../doit3test")
    return {'actions': [
            "rm -rf %s" % test_folder,
            "cp -r %s %s" % (this_folder, test_folder),
            "2to3 --write --nobackups %s" % test_folder,
            "py.test-3.2 %s" % test_folder,
            ],
            'verbosity': 2,
            }


############################ website


DOC_ROOT = 'doc/'
DOC_BUILD_PATH = DOC_ROOT + '_build/html/'

def task_epydoc():
    """# generate API docs"""
    target_path = DOC_BUILD_PATH + 'api/'
    return {'actions':[(create_folder, [target_path]),
                       ("epydoc --config %sepydoc.config " % DOC_ROOT +
                        "-o %(targets)s")],
            'file_dep': CODE_FILES,
            'targets': [target_path]}

def task_sphinx():
    """generate website docs (include analytics)"""
    action = "sphinx-build -b html -d %s_build/doctrees -A include_analytics=1 %s %s"
    return {
        'actions': [action % (DOC_ROOT, DOC_ROOT, DOC_BUILD_PATH)],
        'verbosity': 2,
        }


def task_website():
    """dodo file create website html files"""
    return {'actions': None,
            'task_dep': ['epydoc', 'sphinx'],
            }

def task_website_update():
    """update website on sourceforge"""
    return {'actions': ["rsync -avP -e ssh %s* schettino72,python-doit@web.sourceforge.net:htdocs/" % DOC_BUILD_PATH]}


################### dist


def task_revision():
    """create file with repo rev number"""
    return {'actions': ["hg tip --template '{rev}:{node}' > revision.txt"]}

def task_manifest():
    """create manifest file for distutils """

    def check_version():
        # using a MANIFEST file directly is broken on python2.7
        # http://bugs.python.org/issue11104
        import sys
        assert sys.version_info < (2,7) or sys.version_info > (2,7,2)

    # create manifest will all files under version control without .hg* files
    cmd = """hg manifest | grep -vE ".*\.hg.*" > MANIFEST """
    cmd2 = "echo 'revision.txt' >> MANIFEST"
    return {'actions': [check_version, cmd, cmd2]}

def task_sdist():
    """create source dist package"""
    return {'actions': ["python setup.py sdist"],
            'task_dep': ['revision', 'manifest'],
            }

def task_pypi():
    """upload package to pypi"""
    return {'actions': ["python setup.py sdist upload"],
            'task_dep': ['revision', 'manifest'],
            }




# doit -f ../doit-recipes/deps/deps.py -d . --reporter=executed-only
