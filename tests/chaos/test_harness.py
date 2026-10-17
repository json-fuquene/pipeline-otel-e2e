from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.chaos.common import Docker, SafetyError, http_request, validate_id
from scripts.chaos.load import Load, require_baseline
from scripts.chaos.run import Run


class DockerSafetyTests(unittest.TestCase):
    def test_remote_docker_host_refused_without_probe(self):
        def forbidden(*args, **kwargs):
            self.fail("Remote endpoint must not be probed")

        with self.assertRaises(SafetyError):
            Docker({"DOCKER_HOST": "ssh://remote"}, forbidden)

    def test_tcp_endpoint_is_refused_even_on_loopback(self):
        with self.assertRaises(SafetyError):
            Docker({"DOCKER_HOST": "tcp://127.0.0.1:2375"})

    def test_remote_named_pipe_is_refused(self):
        with self.assertRaises(SafetyError):
            Docker({"DOCKER_HOST": "npipe:////server/pipe/docker_engine"})
        client = Docker({"DOCKER_HOST": "npipe:////./pipe/docker_engine"})
        self.assertEqual(client.endpoint, "npipe:////./pipe/docker_engine")

    def test_context_overrides_host_and_remote_context_is_rejected(self):
        calls = []

        def command(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "ssh://remote\n")

        with self.assertRaises(SafetyError):
            Docker({"DOCKER_CONTEXT": "chosen", "DOCKER_HOST": "unix:///var/run/docker.sock"}, command)
        self.assertEqual(calls, [["docker", "context", "inspect", "chosen", "--format", "{{.Endpoints.docker.Host}}"]])

    def test_local_endpoint_pinned_and_tls_environment_removed(self):
        calls = []

        def command(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, "ok")

        client = Docker({"DOCKER_HOST": "unix:///var/run/docker.sock", "DOCKER_TLS_VERIFY": "1"}, command)
        client.call(["ps"])
        self.assertEqual(calls[0][0][:3], ["docker", "--host", "unix:///var/run/docker.sock"])
        self.assertNotIn("DOCKER_TLS_VERIFY", calls[0][1]["env"])

    def test_command_errors_never_expose_output(self):
        def command(args, **kwargs):
            raise subprocess.CalledProcessError(1, args, output="private-password")

        with self.assertRaises(SafetyError) as raised:
            Docker({"DOCKER_HOST": "unix:///var/run/docker.sock"}, command).call(["ps"])
        self.assertNotIn("private-password", str(raised.exception))

    def test_log_capture_can_include_both_output_streams(self):
        calls = []

        def command(args, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(args, 0, "json-log-from-either-stream")

        client = Docker({"DOCKER_HOST": "unix:///var/run/docker.sock"}, command)
        self.assertEqual(client.call(["logs", "local-id"], merge_output=True), "json-log-from-either-stream")
        self.assertEqual(calls[0]["stderr"], subprocess.STDOUT)
        self.assertNotIn("capture_output", calls[0])

    def test_foreign_container_label_blocks_action(self):
        client = Docker({"DOCKER_HOST": "unix:///var/run/docker.sock"})
        client.call = lambda args: "abc" if args[0] == "ps" else '{"io.pipeline.chaos.run":"other"}'
        with self.assertRaises(SafetyError):
            client.verify("chaos-trial", "trial")

    def test_foreign_volume_blocks_action(self):
        client = Docker({"DOCKER_HOST": "unix:///var/run/docker.sock"})

        def call(args):
            if args[:2] == ["volume", "ls"]:
                return "foreign-volume"
            if args[:2] == ["volume", "inspect"]:
                return '{"io.pipeline.chaos.run":"other"}'
            return ""

        client.call = call
        with self.assertRaises(SafetyError):
            client.verify("chaos-trial", "trial")

    def test_nonloopback_published_port_is_rejected(self):
        client = Docker({"DOCKER_HOST": "unix:///var/run/docker.sock"})
        client.call = lambda args: '{"8000/tcp":[{"HostIp":"0.0.0.0","HostPort":"12345"}]}'
        with self.assertRaises(SafetyError):
            client.port("id", 8000)


class FilesystemTests(unittest.TestCase):
    def test_run_id_rejects_traversal_and_shell_text(self):
        for value in ("../bad", "UPPER", "a;cmd", "-bad", "bad-", "a" * 33, "", "a\nb"):
            with self.subTest(value=value), self.assertRaises(SafetyError):
                validate_id(value)
        for value in ("a", "trial-01", "a" * 32):
            self.assertEqual(validate_id(value), value)

    def test_credentials_are_private_and_separate_from_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Run("trial", root=directory)
            run.new_paths()
            secret = run.private / "env"
            self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
            self.assertEqual(run.private.stat().st_mode & 0o777, 0o700)
            self.assertFalse((run.output / "env").exists())
            self.assertFalse((Path(directory) / ".env").exists())
            with self.assertRaises(FileExistsError):
                run.new_paths()

    def test_symlinked_secret_root_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".chaos").symlink_to(Path(directory))
            with self.assertRaises(SafetyError):
                Run("trial", root=directory).new_paths()

    def test_concurrent_execution_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Run("trial", root=directory)
            run.new_paths()
            with run.lock():
                with self.assertRaises(SafetyError):
                    with run.lock():
                        self.fail("Second lock must not succeed")

    def test_compose_cannot_inherit_ordinary_credentials(self):
        class FakeDocker:
            env = {"POSTGRES_PASSWORD": "ordinary", "CATALOG_DB_PASSWORD": "ordinary", "COMPOSE_FILE": "other"}

            def call(self, args, **kwargs):
                self.args = args
                self.env_used = kwargs["env"]
                return ""

        docker = FakeDocker()
        run = Run("trial", docker=docker)
        run.compose("down")
        self.assertEqual(docker.env_used, {})
        self.assertIn("compose.chaos.yaml", " ".join(docker.args))
        self.assertNotIn("-v", docker.args)


class LoadTests(unittest.TestCase):
    def make_load(self, directory, request):
        return Load({"urls": {"catalog": "http://127.0.0.1:1", "orders": "http://127.0.0.1:2"},
                     "product_id": "product", "order_id": "order"}, Path(directory), request=request)

    def test_remote_http_and_credential_urls_are_rejected_without_io(self):
        for url in ("http://example.com/", "http://user:secret@127.0.0.1:1/", "https://127.0.0.1:1/"):
            with self.assertRaises(SafetyError):
                http_request(url)

    def test_504_preserved_without_retry_or_body(self):
        calls = []

        def request(url, body, request_id):
            calls.append(request_id)
            return 504, {"error": {"code": "catalog_timeout"}, "secret": "private-body"}, request_id

        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, request)
            row = load.attempt("fault", "create", "http://127.0.0.1:2/orders", {})
            self.assertEqual(row["error_code"], "catalog_timeout")
            self.assertEqual(len(calls), 1)
            self.assertFalse(load.abort.is_set())
            self.assertNotIn("private-body", (Path(directory) / "requests.jsonl").read_text())

    def test_readiness_failure_does_not_trigger_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, lambda *args: (503, {}, None))
            load.attempt("fault", "ready_orders", "http://127.0.0.1:2/health/ready")
            self.assertFalse(load.abort.is_set())

    def test_control_failure_triggers_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, lambda *args: (503, {}, None))
            load.attempt("fault", "control_orders", "http://127.0.0.1:2/orders/order")
            self.assertTrue(load.abort.is_set())

    def test_liveness_transport_failure_triggers_abort(self):
        def request(*args):
            raise OSError("private transport details")

        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, request)
            row = load.attempt("fault", "live_orders", "http://127.0.0.1:2/health/live")
            self.assertTrue(load.abort.is_set())
            self.assertEqual(row["transport_error"], "request_failed")

    def test_evidence_write_failure_triggers_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, lambda *args: (200, {}, None))
            with patch("scripts.chaos.load.append_json", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    load.attempt("fault", "control_orders", "http://127.0.0.1:2/orders/order")
            self.assertEqual(load.reason, "capture_failed")

    def test_small_local_schedule_has_no_network_and_records_all_operations(self):
        def request(url, body, request_id):
            return (201, {"id": "00000000-0000-4000-8000-000000000001"}, request_id) if body is not None else (200, {}, request_id)

        with tempfile.TemporaryDirectory() as directory:
            load = self.make_load(directory, request)
            rows = load.phase("baseline", 1)
            self.assertEqual(len(rows), 7)
            self.assertEqual(sum(row["operation"] == "create" for row in rows), 1)

    def test_baseline_rejects_missing_or_slow_samples(self):
        with self.assertRaises(SafetyError):
            require_baseline([])
        rows = [{"operation": operation, "status_code": status, "transport_error": None, "duration_seconds": 0.1}
                for operation, status in (("create", 201), ("control_catalog", 200), ("control_orders", 200)) for _ in range(60)]
        require_baseline(rows)
        for row in rows[:10]:
            row["duration_seconds"] = 2
        with self.assertRaises(SafetyError):
            require_baseline(rows)


class LifecycleTests(unittest.TestCase):
    def make_run(self, directory, state="prepared"):
        run = Run("trial", root=directory)
        run.new_paths()
        run.metadata = {"state": state, "order_id": "seed"}
        run.read = lambda: None
        run.identities = lambda required=None: {"orders", "catalog"}
        run.capture = lambda *args: None
        return run

    def test_invalid_baseline_never_arms_but_does_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory)
            run.metadata.update(target="172.22.0.3", format_version=2)
            run.orders = lambda: ["seed"]
            actions = []

            def auxiliary(action, target=None):
                actions.append(action)
                return {"target": "172.22.0.3", "state": "idle"}

            run.auxiliary = auxiliary
            with patch("scripts.chaos.run.Load") as loader, patch("builtins.print"), \
                    patch("scripts.chaos.run.Telemetry") as telemetry, patch("scripts.chaos.run.time.sleep"):
                loader.return_value.phase.return_value = []
                loader.return_value.reason = None
                telemetry.return_value.stop.return_value = {"catalog": [], "orders": []}
                with self.assertRaises(SafetyError):
                    run.run()
            self.assertNotIn("arm", actions)
            self.assertIn("rollback", actions)
            self.assertEqual(run.metadata["state"], "aborted")

    def test_failed_prepare_can_stop_partial_project_without_removing_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory, "prepare_failed")
            calls = []
            run.compose = lambda *args, **kwargs: calls.append(args)
            self.assertEqual(run.control("down")["injection"], "never_started")
            self.assertEqual(calls, [("down",)])
            self.assertEqual(run.metadata["state"], "stopped")

    def test_unverified_cleanup_prevents_compose_down(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory, "cleanup_unverified")
            run.auxiliary = lambda action: {"state": "cleanup_failed"}
            calls = []
            run.compose = lambda *args, **kwargs: calls.append(args)
            with self.assertRaises(SafetyError):
                run.control("down")
            self.assertEqual(calls, [])

    def test_logs_redact_generated_passwords(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory)
            values = [line.split("=", 1)[1] for line in (run.private / "env").read_text().splitlines() if "PASSWORD=" in line]
            run.compose = lambda *args, **kwargs: "password=" + values[0]
            Run.capture(run)
            logs = (run.output / "logs" / "orders.log").read_text()
            self.assertNotIn(values[0], logs)
            self.assertIn("[REDACTED]", logs)

    def test_partial_prepare_status_never_requires_auxiliary(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory, "prepare_failed")
            self.assertEqual(run.control("status")["injection"], "never_started")

    def test_prepare_refuses_existing_id_before_any_docker_call(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory)
            run.connect = lambda: self.fail("No Docker call expected")
            with self.assertRaises(SafetyError):
                run.prepare()

    def test_idle_supervisor_with_orphan_rules_cannot_report_clean_status(self):
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(directory, "aborted")

            def auxiliary(action):
                if action == "status":
                    return {"state": "idle"}
                raise SafetyError("Orphaned rules found after auxiliary restart")

            run.auxiliary = auxiliary
            with self.assertRaises(SafetyError):
                run.control("status")


if __name__ == "__main__":
    unittest.main()
