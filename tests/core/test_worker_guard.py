"""A second server process on the same data directory is refused (application/core/worker_guard.py)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from application.core import worker_guard
from application.core.worker_guard import SecondWorkerError, claim_single_worker, release

ROOT = Path(__file__).resolve().parents[2]


def _other_process(data_dir, env_extra=None):
    """Try to claim *data_dir* from a separate Python process; returns the finished process."""
    code = (
        'import sys; from application.core.worker_guard import claim_single_worker, SecondWorkerError\n'
        'try:\n    claim_single_worker(sys.argv[1])\nexcept SecondWorkerError as e:\n    print(e); sys.exit(7)\n'
    )
    env = {**os.environ, **(env_extra or {}), 'PYTHONPATH': str(ROOT)}
    return subprocess.run([sys.executable, '-c', code, str(data_dir)], capture_output=True, text=True, env=env, cwd=ROOT)


@pytest.fixture()
def data_dir(tmp_path):
    yield str(tmp_path)
    release(str(tmp_path))


def test_the_first_process_gets_the_lock_and_a_second_one_is_refused(data_dir):
    claim_single_worker(data_dir, environ={})
    result = _other_process(data_dir)
    assert result.returncode == 7
    assert f'pid {os.getpid()}' in result.stdout
    assert 'exactly one worker' in result.stdout


def test_claiming_twice_in_one_process_is_fine(data_dir):
    claim_single_worker(data_dir, environ={})
    claim_single_worker(data_dir, environ={})        # the app built twice in one process (tests, reloads in dev)


def test_the_lock_is_free_again_when_the_holder_is_gone(data_dir):
    claim_single_worker(data_dir, environ={})
    release(data_dir)
    assert _other_process(data_dir).returncode == 0


def test_other_data_directories_do_not_interfere(data_dir, tmp_path_factory):
    claim_single_worker(data_dir, environ={})
    other = tmp_path_factory.mktemp('other')
    assert _other_process(other).returncode == 0


@pytest.mark.parametrize('value', ['2', '4'])
def test_asking_for_more_workers_is_refused(data_dir, value):
    with pytest.raises(SecondWorkerError, match='WEB_CONCURRENCY'):
        claim_single_worker(data_dir, environ={'WEB_CONCURRENCY': value})


@pytest.mark.parametrize('value', ['1', '', 'many', None])
def test_one_worker_or_nonsense_is_not_a_refusal(data_dir, value):
    environ = {} if value is None else {'WEB_CONCURRENCY': value}
    claim_single_worker(data_dir, environ=environ)


def test_the_module_keeps_no_lock_for_a_cli_run(tmp_path):
    # `create_app(startup=False)` (flask dh …, tests) never calls the guard: nothing is held for a fresh dir.
    assert not any(str(tmp_path) in path for path in worker_guard._held)


def test_a_crashed_holder_leaves_a_stale_file_but_not_the_lock(tmp_path):
    # The lock belongs to the process, not to the file: when the holder dies without cleaning up
    # (kill -9, out of memory, power cut) the operating system drops it and the file stays behind.
    code = (
        'import sys, time; from application.core.worker_guard import claim_single_worker\n'
        'claim_single_worker(sys.argv[1]); print("held", flush=True); time.sleep(60)\n'
    )
    holder = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.PIPE, text=True,
                              env={**os.environ, 'PYTHONPATH': str(ROOT)}, cwd=ROOT)
    try:
        assert holder.stdout.readline().strip() == 'held'
        assert _other_process(tmp_path).returncode == 7          # refused while it lives
        holder.kill()                                            # SIGKILL: no chance to clean up
        holder.wait(timeout=10)
        assert (tmp_path / worker_guard.LOCK_NAME).exists()      # the stale file is still there …
        assert _other_process(tmp_path).returncode == 0          # … but the next start gets the lock
    finally:
        holder.kill()
        holder.wait(timeout=10)
        release(str(tmp_path))
