"""Exercise the workflow's shell steps without making network requests."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Requires Bash on POSIX')
class DeployWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = yaml.safe_load((ROOT / '.github/workflows/instagram-sync.yml').read_text())
        cls.sync_step, cls.hook_step = config['jobs']['sync']['steps'][-2:]

    def test_only_a_successful_push_enables_the_deploy_step(self):
        self.assertEqual(
            self.hook_step['if'],
            "steps.sync_content.outputs.pushed == 'true' && github.event.repository.name != format('{0}.github.io', github.repository_owner)",
        )
        stub = '''
git() {
  case "$1" in
    diff) [[ "$MODE" == no-changes ]];;
    push) [[ "$MODE" == pushed ]];;
    *) return 0;;
  esac
}
python() { return 0; }
npm() { return 0; }
'''
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, 'output')
            for mode, status, expected in [
                ('no-changes', 0, ''), ('failed-push', 1, ''), ('pushed', 0, 'pushed=true\n'),
            ]:
                with self.subTest(mode=mode):
                    output.write_text('')
                    result = subprocess.run(
                        ['bash', '-c', stub + self.sync_step['run']],
                        env={**os.environ, 'BRANCH': 'main', 'MODE': mode, 'GITHUB_OUTPUT': str(output)},
                        text=True, capture_output=True, timeout=5, check=False,
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(output.read_text(), expected)

    def test_root_pages_deployment_uses_explicit_workflow_dispatch_after_bot_push(self):
        config = yaml.safe_load((ROOT / '.github/workflows/instagram-sync.yml').read_text())
        dispatch = config['jobs']['dispatch_pages']
        self.assertEqual(dispatch['needs'], 'sync')
        self.assertEqual(config['jobs']['sync']['outputs']['pushed'], '${{ steps.sync_content.outputs.pushed }}')
        self.assertEqual(dispatch['permissions'], {'actions': 'write'})
        self.assertEqual(
            dispatch['if'],
            "needs.sync.outputs.pushed == 'true' && github.event.repository.name == format('{0}.github.io', github.repository_owner)",
        )
        self.assertIn('gh workflow run deploy-pages.yml', dispatch['steps'][0]['run'])
        deploy = yaml.safe_load((ROOT / '.github/workflows/deploy-pages.yml').read_text())
        self.assertIn('workflow_dispatch', deploy[True])  # PyYAML reads unquoted "on" as a boolean.
        self.assertEqual(deploy[True]['push']['branches'], ['main'])

    def run_hook(self, url, status='202', curl_exit=0):
        stub = '''
curl() {
  [[ " $* " == *" -X POST $DEPLOY_WEBHOOK_URL " ]] || return 99
  printf '%s' "$HTTP_STATUS"
  return "$CURL_EXIT"
}
'''
        return subprocess.run(
            ['bash', '-c', stub + self.hook_step['run']],
            env={**os.environ, 'DEPLOY_WEBHOOK_URL': url, 'HTTP_STATUS': status, 'CURL_EXIT': str(curl_exit)},
            text=True, capture_output=True, timeout=5, check=False,
        )

    def test_empty_hook_skips_the_request(self):
        result = self.run_hook('', '500')
        self.assertEqual(result.returncode, 0)
        self.assertIn('No deploy hook configured', result.stdout)

    def test_hook_posts_only_to_https_and_does_not_print_the_url(self):
        url = 'https://provider.invalid/private-deploy-token'
        result = self.run_hook(url)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Deployment requested', result.stdout)
        self.assertNotIn(url, result.stdout + result.stderr)
        self.assertEqual(self.run_hook(url.replace('https:', 'http:')).returncode, 1)

    def test_hook_failure_distinguishes_transport_and_http_errors_after_push(self):
        url = 'https://provider.invalid/private-deploy-token'
        for status, exit_code, message in [('302', 0, 'HTTP 302'), ('503', 0, 'HTTP 503'), ('000', 28, 'could not be reached')]:
            with self.subTest(status=status):
                result = self.run_hook(url, status, exit_code)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertIn('import commit is already pushed', result.stderr)
                self.assertNotIn(url, result.stdout + result.stderr)
