# SPDX-License-Identifier: MIT
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import environment


class Engine:
    def __init__(self):
        self.calls = []
        self.exists = False
        self.ids = ['a' * 64, 'b' * 64]
        self.annotation = None
        self.kind_version = 'kind v0.33.0 go1.26 linux/amd64'
        self.fail_create = False
        self.fail_apply = False
        self.api_down = False
        self.endpoint = 'unix:///var/run/docker.sock'

    def run(self, command, **options):
        self.calls.append((command, options))
        out, code = '', 0
        if command[:2] == ['kind', 'version']:
            out = self.kind_version
        elif command[:3] == ['kind', 'get', 'clusters']:
            out = 'cks-test\n' if self.exists else ''
        elif command[:3] == ['kind', 'create', 'cluster']:
            self.exists = True
            if self.fail_create:
                code = 1
            else:
                Path(command[command.index('--kubeconfig') + 1]).write_text('private fixture config')
        elif command[:3] == ['kind', 'delete', 'cluster']:
            self.exists = False
        elif command[:2] == ['docker', 'info']:
            out = 'linux'
        elif command[:3] == ['docker', 'context', 'inspect']:
            out = self.endpoint
        elif command[:2] == ['docker', 'ps']:
            out = '\n'.join(self.ids) if self.exists else ''
        elif command[:2] == ['kubectl', 'version']:
            out = json.dumps({'clientVersion': {'gitVersion': 'v1.37.0'}})
        elif command[0] == 'kubectl':
            args = command[7:]
            if args[:2] == ['get', 'namespace']:
                code = int(self.api_down)
                out = json.dumps({'metadata': {'uid': 'namespace-uid', 'annotations':
                                  {'cks-practice/environment-id': self.annotation} if self.annotation else {}}})
            elif args[:2] == ['annotate', 'namespace']:
                self.annotation = next(a.split('=', 1)[1] for a in args if a.startswith('cks-practice/environment-id='))
            elif args[:1] == ['apply'] and self.fail_apply:
                code = 1
            elif args[:1] == ['exec']:
                out = 'cks-practice\n'
            else:
                out = ''
        elif command[0] == environment.sys.executable:
            out = 'PASS: preflight\n'
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, code, out, 'controlled failure' if code else '')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('labs/environments/kind.yaml', 'labs/fixtures/workloads.yaml', 'scripts/lab.py'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        self.engine = Engine()
        self.body = b'known calico manifest'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(environment, 'ROOT', self.root))
        self.stack.enter_context(patch.dict(os.environ, {'DOCKER_HOST': '', 'DOCKER_CONTEXT': ''}))
        self.stack.enter_context(patch.object(environment, 'CALICO_SHA', hashlib.sha256(self.body).hexdigest()))
        self.stack.enter_context(patch('scripts.environment.shutil.which', return_value='/bin/tool'))
        self.stack.enter_context(patch('scripts.environment.subprocess.run', side_effect=self.engine.run))
        self.download = self.stack.enter_context(patch('scripts.environment.urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(self.body)))

    def invoke(self, action, name='cks-test'):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = environment.main([action, '--name', name])
        return result, output.getvalue()

    @property
    def directory(self):
        return self.root / 'work/environments/cks-test'

    def test_create_has_private_credentials_explicit_context_and_no_solutions(self):
        code, output = self.invoke('create')
        self.assertEqual(code, 0, output)
        self.assertIn('export KUBECONFIG=', output)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.directory / 'kubeconfig').stat().st_mode & 0o777, 0o600)
        metadata = json.loads((self.directory / 'environment.json').read_text())
        self.assertEqual(metadata['phase'], 'ready')
        self.assertEqual(metadata['namespace_uid'], 'namespace-uid')
        for command, options in self.engine.calls:
            self.assertNotIn('solutions', ' '.join(command))
            if command[0] == 'kubectl' and command[1] != 'version':
                self.assertIn(str(self.directory / 'kubeconfig'), command)
                self.assertIn('kind-cks-test', command)
            self.assertEqual(options['env']['KUBECONFIG'], str(self.directory / 'kubeconfig'))

    def test_existing_cluster_is_never_adopted(self):
        self.engine.exists = True
        self.assertEqual(self.invoke('create')[0], 1)
        self.assertFalse(self.directory.exists())
        self.assertFalse(any(cmd[:3] == ['kind', 'create', 'cluster'] for cmd, _ in self.engine.calls))

    def test_existing_or_symlinked_directory_is_preserved(self):
        self.directory.parent.mkdir(parents=True)
        target = self.root / 'elsewhere'
        target.mkdir()
        self.directory.symlink_to(target, target_is_directory=True)
        self.assertEqual(self.invoke('create')[0], 1)
        self.assertEqual(list(target.iterdir()), [])

    def test_corrupt_download_never_creates_or_applies_cluster(self):
        with patch.object(environment, 'CALICO_SHA', '0' * 64):
            self.assertEqual(self.invoke('create')[0], 1)
        self.assertFalse(any(cmd[:3] == ['kind', 'create', 'cluster'] for cmd, _ in self.engine.calls))
        self.assertEqual(self.invoke('delete')[0], 0)

    def test_incompatible_tools_do_not_create_resources(self):
        self.engine.kind_version = 'kind v0.11.1 go1.16 linux/amd64'
        self.assertEqual(self.invoke('create')[0], 1)
        self.assertFalse(self.directory.exists())
        with patch('scripts.environment.shutil.which', return_value=None):
            self.assertEqual(self.invoke('create')[0], 1)

    def test_remote_docker_context_is_not_used(self):
        self.engine.endpoint = 'ssh://example.invalid'
        with patch.dict(os.environ, {'DOCKER_HOST': 'unix:///var/run/docker.sock', 'DOCKER_CONTEXT': 'remote'}):
            self.assertEqual(self.invoke('create')[0], 1)
        self.assertFalse(self.directory.exists())

    def test_failed_kind_creation_does_not_delete_unattested_containers(self):
        self.engine.fail_create = True
        self.assertEqual(self.invoke('create')[0], 1)
        code, output = self.invoke('delete')
        self.assertEqual(code, 1, output)
        self.assertTrue(self.engine.exists)
        self.assertFalse(any(cmd[:3] == ['kind', 'delete', 'cluster'] for cmd, _ in self.engine.calls))

    def test_failure_after_ownership_can_be_cleaned_up_without_api(self):
        self.engine.fail_apply = True
        self.assertEqual(self.invoke('create')[0], 1)
        self.engine.api_down = True
        code, output = self.invoke('delete')
        self.assertEqual(code, 0, output)
        self.assertFalse(self.engine.exists)
        self.assertFalse(self.directory.exists())

    def test_changed_marker_or_container_ids_prevent_deletion(self):
        self.assertEqual(self.invoke('create')[0], 0)
        original = self.engine.annotation
        self.engine.annotation = 'another-owner'
        self.assertEqual(self.invoke('delete')[0], 1)
        self.engine.annotation = original
        self.engine.ids = ['c' * 64]
        self.assertEqual(self.invoke('delete')[0], 1)
        self.assertTrue(self.engine.exists)

    def test_delete_preserves_extra_learner_files(self):
        self.assertEqual(self.invoke('create')[0], 0)
        notes = self.directory / 'notes.txt'
        notes.write_text('keep my observations')
        self.assertEqual(self.invoke('delete')[0], 0)
        self.assertEqual(notes.read_text(), 'keep my observations')
        self.assertFalse((self.directory / 'kubeconfig').exists())

    def test_status_reads_without_cluster_mutation(self):
        self.assertEqual(self.invoke('create')[0], 0)
        self.engine.calls.clear()
        code, output = self.invoke('status')
        self.assertEqual(code, 0, output)
        self.assertIn('ready', output)
        self.assertFalse(any('create' in cmd or 'delete' in cmd or 'annotate' in cmd for cmd, _ in self.engine.calls))

    def test_readiness_watch_can_use_its_documented_wait(self):
        self.assertEqual(self.invoke('create')[0], 0)
        watches = [(cmd, options) for cmd, options in self.engine.calls if 'rollout' in cmd]
        self.assertTrue(watches)
        for command, options in watches:
            self.assertEqual(command[command.index('--request-timeout') + 1], str(options['timeout']) + 's')

    def test_invalid_name_never_runs_a_tool(self):
        for name in ['production', 'cks-../other', 'cks--', 'cks-' + 'x' * 64]:
            with self.subTest(name=name):
                self.assertEqual(self.invoke('create', name)[0], 1)
        self.assertEqual(self.engine.calls, [])


if __name__ == '__main__':
    unittest.main()
