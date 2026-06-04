import importlib.util
import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK_CUDA_PY = REPO_ROOT / 'recipes' / 'checkCudaVersion.py'
SPEC = importlib.util.spec_from_file_location('check_cuda_version', CHECK_CUDA_PY)
check_cuda_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_cuda_version)


class CheckCudaVersionTests(unittest.TestCase):
    def test_parses_pytorch_cuda_version_after_shell_warning(self):
        output = (
            'bash: /opt/conda/lib/libtinfo.so.6: no version information '
            'available (required by bash)\n'
            '11.8\n'
        )

        self.assertEqual(check_cuda_version._parse_pytorch_cuda_version(output), '11.8')

    def test_treats_pytorch_without_cuda_as_missing(self):
        output = (
            'bash: /opt/conda/lib/libtinfo.so.6: no version information '
            'available (required by bash)\n'
            'None\n'
        )

        self.assertIsNone(check_cuda_version._parse_pytorch_cuda_version(output))


if __name__ == '__main__':
    unittest.main()
