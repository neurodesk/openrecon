import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK_ROOT_USER_PY = REPO_ROOT / 'recipes' / 'checkRootUser.py'
SPEC = importlib.util.spec_from_file_location('check_root_user', CHECK_ROOT_USER_PY)
check_root_user = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_root_user)


class CheckRootUserTests(unittest.TestCase):
    def test_parses_uid_after_shell_warning(self):
        output = (
            'bash: /opt/conda/lib/libtinfo.so.6: no version information '
            'available (required by bash)\n'
            '0\n'
        )

        self.assertEqual(check_root_user._parse_user_id(output), 0)

    def test_rejects_output_without_uid(self):
        output = (
            'bash: /opt/conda/lib/libtinfo.so.6: no version information '
            'available (required by bash)\n'
        )

        with self.assertRaises(ValueError):
            check_root_user._parse_user_id(output)


if __name__ == '__main__':
    unittest.main()
