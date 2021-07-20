import os

import servicex


class TestAppInit:
    def test_read_from_config(self):
        os.environ['APP_CONFIG_FILE'] = str(os.path.join(os.path.dirname(__file__),
                                                         "test.config"))
        app = servicex.create_app()
        assert app.config['FOO'] == 'bar'
        assert app.config['SECRET_VALUE'] == 'blah'
        assert not app.config['BOOL_VALUE']

        os.environ['SECRET_VALUE'] = 'shhh'
        os.environ['BOOL_VALUE'] = 'true'
        app_from_env = servicex.create_app()
        assert app_from_env.config['SECRET_VALUE'] == 'shhh'
        assert app_from_env.config['BOOL_VALUE']
