import pickle

import pytest

from doit.cmdparse import DefaultUpdate, CmdParseError, CmdOption, CmdParse



class TestDefaultUpdate(object):
    def test(self):
        du = DefaultUpdate()

        du.set_default('a', 0)
        du.set_default('b', 0)

        assert 0 == du['a']
        assert 0 == du['b']

        du['b'] = 1
        du.update_defaults({'a':2, 'b':2})
        assert 2 == du['a']
        assert 1 == du['b']

    # http://bugs.python.org/issue826897
    def test_pickle(self):
        du = DefaultUpdate()
        du.set_default('x', 0)
        dump = pickle.dumps(du,2)
        pickle.loads(dump)


class TestCmdOption(object):

    def test_non_required_fields(self):
        opt1 = CmdOption({'name':'op1', 'default':''})
        assert '' == opt1.long

    def test_invalid_field(self):
        opt_dict = {'name':'op1', 'default':'', 'non_existent':''}
        pytest.raises(CmdParseError, CmdOption, opt_dict)

    def test_missing_field(self):
        opt_dict = {'name':'op1', 'long':'abc'}
        pytest.raises(CmdParseError, CmdOption, opt_dict)



opt_bool = {'name': 'flag',
            'short':'f',
            'long': 'flag',
            'inverse':'no-flag',
            'type': bool,
            'default': False,
            'help': 'help for opt1'}

opt_rare = {'name': 'rare',
            'long': 'rare-bool',
            'type': bool,
            'default': False,
            'help': 'help for opt2'}

opt_int = {'name': 'num',
           'short':'n',
           'long': 'number',
           'type': int,
           'default': 5,
           'help': 'help for opt3'}

opt_no = {'name': 'no',
          'short':'',
          'long': '',
          'type': int,
          'default': 5,
          'help': 'user cant modify me'}


class TestCommand(object):

    @pytest.fixture
    def cmd(self, request):
        opt_list = (opt_bool, opt_rare, opt_int, opt_no)
        options = [CmdOption(o) for o in opt_list]
        cmd = CmdParse(options)
        return cmd


    def test_short(self, cmd):
        assert "fn:" == cmd.get_short(), cmd.get_short()

    def test_long(self, cmd):
        assert ["flag", "no-flag", "rare-bool", "number="] == cmd.get_long()

    def test_getOption(self, cmd):
        # short
        opt, is_inverse = cmd.get_option('-f')
        assert (opt_bool['name'], False) == (opt.name, is_inverse)
        # long
        opt, is_inverse = cmd.get_option('--rare-bool')
        assert (opt_rare['name'], False) == (opt.name, is_inverse)
        # inverse
        opt, is_inverse = cmd.get_option('--no-flag')
        assert (opt_bool['name'], True) == (opt.name, is_inverse)
        # not found
        opt, is_inverse = cmd.get_option('not-there')
        assert (None, None) == (opt, is_inverse)


    def test_parseDefaults(self, cmd):
        params, args = cmd.parse([])
        assert False == params['flag']
        assert 5 == params['num']

    def test_parseShortValues(self, cmd):
        params, args = cmd.parse(['-n','89','-f'])
        assert True == params['flag']
        assert 89 == params['num']

    def test_parseLongValues(self, cmd):
        params, args = cmd.parse(['--rare-bool','--num','89', '--no-flag'])
        assert True == params['rare']
        assert False == params['flag']
        assert 89 == params['num']

    def test_parsePositionalArgs(self, cmd):
        params, args = cmd.parse(['-f','p1','p2','--sub-arg'])
        assert ['p1','p2','--sub-arg'] == args

    def test_parseWrongType(self, cmd):
        pytest.raises(CmdParseError, cmd.parse, ['--num','oi'])
