# SPDX-License-Identifier: MIT
"""Create, inspect and remove an owned local kind practice environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
CALICO_URL = 'https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml'
CALICO_SHA = '2de8f47595fb9c41b3f47d7b767a1f8e72ecf84057af834738ff12689a234da5'
MARKER = 'cks-practice/environment-id'


class Error(Exception):
    pass


class CommandError(Error):
    pass


class Environment:
    def __init__(self, name):
        if len(name) > 63 or not re.fullmatch(r'cks-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', name):
            raise Error('Use a DNS-safe name beginning cks-, at most 63 characters.')
        self.name = name
        self.context = 'kind-' + name
        self.directory = ROOT / 'work' / 'environments' / name
        self.config = self.directory / 'kubeconfig'
        self.state_file = self.directory / 'environment.json'
        self.env = dict(os.environ, KUBECONFIG=str(self.config))
        for path in (ROOT / 'work', self.directory.parent, self.directory):
            if path.is_symlink():
                raise Error(f'Refusing symbolic link: {path}')

    def run(self, *command, timeout=30):
        try:
            result = subprocess.run(list(command), cwd=ROOT, env=self.env,
                                    capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise CommandError(f'{command[0]} {command[1]} could not finish; check the tool and local engine.') from None
        if result.returncode:
            raise CommandError(f'{command[0]} {command[1]} failed; inspect this environment before retrying.')
        return result.stdout.strip()

    def kube(self, *args, timeout=30):
        return self.run('kubectl', '--kubeconfig', str(self.config), '--context', self.context,
                        '--request-timeout', str(timeout) + 's', *args, timeout=timeout)

    def tools(self, create=False):
        for name in ('kind', 'docker', 'kubectl') if create else ('kind', 'docker'):
            if not shutil.which(name):
                raise Error(f'Install {name} using the environment guide, then retry.')
        endpoint = self.env.get('DOCKER_HOST') if not self.env.get('DOCKER_CONTEXT') else None
        endpoint = endpoint or self.run('docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}')
        if not endpoint.startswith(('unix://', 'npipe://')):
            raise Error('Use a local Docker socket/context for this local practice profile.')
        if self.run('docker', 'info', '--format', '{{.OSType}}') != 'linux':
            raise Error('The kind profile needs a Docker engine running Linux containers.')
        if create:
            if not re.match(r'^kind v0\.33\.0(?:\s|$)', self.run('kind', 'version')):
                raise Error('Install kind v0.33.0 to match the pinned practice profile.')
            try:
                version = json.loads(self.run('kubectl', 'version', '--client', '-o', 'json'))['clientVersion']['gitVersion']
            except (ValueError, KeyError, TypeError):
                raise Error('Could not read the kubectl client version.') from None
            if not re.match(r'^v1\.37\.', version):
                raise Error('Use kubectl 1.37.x with this Kubernetes 1.37 profile.')

    def clusters(self):
        return self.run('kind', 'get', 'clusters').splitlines()

    def containers(self):
        values = sorted(self.run('docker', 'ps', '-aq', '--no-trunc', '--filter',
                                 f'label=io.x-k8s.kind.cluster={self.name}').splitlines())
        if any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in values):
            raise Error('Docker returned unexpected container identities.')
        return values

    def save(self, state):
        with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, delete=False, encoding='utf-8') as file:
            json.dump(state, file, indent=2)
            temporary = Path(file.name)
        temporary.replace(self.state_file)

    def load(self):
        if self.state_file.is_symlink() or self.config.is_symlink():
            raise Error('Refusing linked ownership metadata or kubeconfig.')
        try:
            state = json.loads(self.state_file.read_text())
            uuid.UUID(state['owner'])
            valid = state['name'] == self.name and state['phase'] in {'reserved', 'created', 'owned', 'ready'}
            valid &= isinstance(state['containers'], list)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise Error(f'No valid ownership record at {self.state_file}. No resources were adopted.') from None
        if not valid:
            raise Error('Ownership record does not match this environment.')
        return state

    def namespace(self):
        try:
            return json.loads(self.kube('get', 'namespace', 'kube-system', '-o', 'json'))['metadata']
        except (ValueError, KeyError, TypeError):
            raise Error('The cluster returned unexpected ownership metadata.') from None

    def ownership(self, state):
        current = self.containers()
        if not current:
            if self.name in self.clusters():
                raise Error('Cluster name exists without the recorded Docker identities; inspect it manually.')
            return False
        if not state['containers'] or current != state['containers']:
            raise Error('Container ownership differs or creation did not establish ownership. Nothing will be deleted.')
        if not shutil.which('kubectl'):
            print('INFO: API check unavailable; exact owned Docker identities match.')
            return True
        try:
            metadata = self.namespace()
        except CommandError:
            print('INFO: API unavailable; exact owned Docker identities match for recovery.')
            return True
        marker = metadata.get('annotations', {}).get(MARKER)
        if state.get('namespace_uid') and metadata.get('uid') != state['namespace_uid']:
            raise Error('The cluster UID changed. Nothing will be deleted.')
        if marker != state['owner'] and not (state['phase'] == 'created' and marker is None):
            raise Error('The cluster ownership marker changed. Nothing will be deleted.')
        return True

    def create(self):
        self.tools(create=True)
        if self.name in self.clusters() or self.containers():
            raise Error(f'Cluster {self.name} already exists. Choose a fresh name; existing clusters are never adopted.')
        for parent in (ROOT / 'work', self.directory.parent):
            parent.mkdir(mode=0o700, exist_ok=True)
        try:
            self.directory.mkdir(mode=0o700)
        except FileExistsError:
            raise Error(f'{self.directory} already exists. Use status/delete or choose a fresh name.') from None
        state = {'name': self.name, 'owner': str(uuid.uuid4()), 'phase': 'reserved', 'containers': []}
        self.save(state)
        print('Preparing the checksum-pinned networking manifest...', flush=True)
        try:
            with urllib.request.urlopen(CALICO_URL, timeout=60) as response:
                body = response.read(8 * 1024 * 1024 + 1)
        except (OSError, urllib.error.URLError):
            raise Error('Calico download failed; no cluster was created.') from None
        if hashlib.sha256(body).hexdigest() != CALICO_SHA:
            raise Error('Calico checksum mismatch; no manifest was applied and no cluster was created.')
        manifest = self.directory / 'calico.yaml'
        manifest.write_bytes(body)
        manifest.chmod(0o600)
        print(f'Creating {self.name} with an isolated kubeconfig...', flush=True)
        self.run('kind', 'create', 'cluster', '--name', self.name, '--config', str(ROOT / 'labs/environments/kind.yaml'),
                 '--kubeconfig', str(self.config), timeout=600)
        state.update(phase='created', containers=self.containers())
        if not state['containers']:
            raise Error('Creation returned without owned Docker nodes; inspect the environment manually.')
        self.save(state)
        if self.config.is_symlink() or not self.config.is_file():
            raise Error('kind did not write a regular isolated kubeconfig.')
        self.config.chmod(0o600)
        metadata = self.namespace()
        state['namespace_uid'] = metadata['uid']
        self.save(state)
        self.kube('annotate', 'namespace', 'kube-system', f'{MARKER}={state["owner"]}')
        state['phase'] = 'owned'
        self.save(state)
        print('Installing Calico and waiting for nodes and DNS...', flush=True)
        self.kube('apply', '-f', str(manifest), timeout=120)
        for resource in ('daemonset/calico-node', 'deployment/calico-kube-controllers', 'deployment/coredns'):
            self.kube('-n', 'kube-system', 'rollout', 'status', resource, '--timeout=300s', timeout=330)
        self.kube('wait', 'nodes', '--all', '--for=condition=Ready', '--timeout=180s', timeout=210)
        print(self.run(sys.executable, str(ROOT / 'scripts/lab.py'), '--context', self.context, 'preflight', timeout=180))
        print('Preparing the five baseline witnesses...', flush=True)
        self.kube('apply', '-f', str(ROOT / 'labs/fixtures/workloads.yaml'), timeout=120)
        for namespace in ('cks-lab', 'cks-other'):
            self.kube('wait', '-n', namespace, 'pods', '--all', '--for=condition=Ready', '--timeout=180s', timeout=210)
        for namespace, pod, destination in [('cks-lab', 'client', 'cks-lab'), ('cks-lab', 'intruder', 'cks-lab'),
                                             ('cks-other', 'client', 'cks-lab'), ('cks-lab', 'client', 'cks-other')]:
            page = self.kube('exec', '-n', namespace, pod, '--', 'wget', '-qO-', '-T', '3',
                             f'http://api.{destination}.svc:8080/')
            if page != 'cks-practice':
                raise Error('A baseline witness returned an unexpected page; inspect the application before practice.')
        state['phase'] = 'ready'
        self.save(state)
        print('PASS: environment and unrestricted baseline are ready. Start CS01 in preparation/LAB-SAFETY.md.')
        self.exports()

    def exports(self):
        print('export KUBECONFIG=' + shlex.quote(str(self.config)))
        print('export LAB_CONTEXT=' + shlex.quote(self.context))

    def status(self):
        self.tools()
        state = self.load()
        if not self.ownership(state):
            raise Error('Cluster is absent. Run delete to remove its remaining local credentials.')
        print(f'{self.name}: recorded phase={state["phase"]}')
        print(self.kube('get', 'nodes', '-o', 'wide'))
        self.exports()

    def delete(self):
        self.tools()
        state = self.load()
        if self.ownership(state):
            print(f'Deleting owned cluster {self.name}...', flush=True)
            self.run('kind', 'delete', 'cluster', '--name', self.name, '--kubeconfig', str(self.config), timeout=180)
            if self.containers() or self.name in self.clusters():
                raise Error('Cluster deletion has not completed; local recovery metadata was retained.')
        for name in ('kubeconfig', 'calico.yaml', 'environment.json'):
            path = self.directory / name
            if path.is_symlink():
                raise Error('Refusing linked local artifacts; inspect the environment directory.')
            path.unlink(missing_ok=True)
        if not any(self.directory.iterdir()):
            self.directory.rmdir()
        print('PASS: owned cluster and credentials removed; any additional learner files were preserved.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('create', 'status', 'delete'))
    parser.add_argument('--name', default='cks-practice', help='Owned cluster name beginning cks-')
    args = parser.parse_args(argv)
    environment = None
    try:
        environment = Environment(args.name)
        getattr(environment, args.action)()
        return 0
    except (Error, OSError, KeyboardInterrupt) as error:
        print(f'ERROR: {error or "interrupted"}')
        if environment and environment.state_file.exists():
            print(f'Local recovery record: {environment.state_file}')
            print(f'Run this script with status or delete --name {environment.name}.')
            print('If ownership was not established, inspect kind get clusters and the matching Docker nodes before manual removal.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
